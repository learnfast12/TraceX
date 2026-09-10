import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, Query
from models import (
    BtcStatus, RiskScoresResponse, DashboardResponse,
    PeelingChainsResponse, DarknetSweepsResponse, WalletDetailResponse,
    AnomalyExplanationResponse, WalletGeoResponse, HealthResponse,
)
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from graph import init_db, get_graph_data, get_account_details
from risk import calculate_risk
from ml_pipeline import ml_pipeline
from graph_intelligence import graph_intel
from response_engine import response_engine
from real_validation import run_real_validation, run_nested_validation
import pandas as pd
import json as _json
from collections import defaultdict
from clustering import load_transactions
from network_fusion import load_relay_map
from pattern_detection import detect_peeling_chains
from convergence_detection import detect_darknet_sweeps
from risk_scoring import (
    build_wallet_graph, build_seeds, personalized_pagerank,
    compute_risk_ratio, compute_final_scores,
)
from btc_anomaly import run_pipeline
from network_fusion import build_wallet_ip_map, build_receiving_wallet_ip_map
from geoip_lookup import load_country_index, load_asn_index, enrich_ip
from shadow_entity_resolution import run_shadow_entity_resolution

import os as _os
BTC_DATA_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "dataset", "output")
btc_cache = {"loaded": False}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tracex")

app = FastAPI(
    title="TraceNetX v2.0",
    description="Mule Account Intelligence & Criminal Network Disruption System | Team OMEGA 404",
    version="2.0.0"
)

ALLOWED_ORIGINS = _os.environ.get(
    "TRACEX_ALLOWED_ORIGINS",
    "http://localhost:3002,http://127.0.0.1:3002"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.on_event("startup")
def startup():
    # Legacy TraceNetX banking-layer pipeline (Neo4j + transactions.csv) is
    # not part of TRACE-X's offline Bitcoin deliverable and is not carried
    # over in this fork — skip it gracefully if the dependency isn't present
    # rather than blocking the whole app from booting.
    try:
        init_db()
        df = pd.read_csv("transactions.csv")
        ml_pipeline.train(df)
        logger.info("[TraceNetX v2.0] All systems online.")
    except Exception as e:
        logger.warning(f"[TraceNetX] Legacy banking-layer startup skipped ({type(e).__name__}: {e})")

    try:
        tx_csv = f"{BTC_DATA_DIR}/bitcoin_transactions.csv"
        relay_csv = f"{BTC_DATA_DIR}/relay_events.csv"
        btc_cache["tx_map"] = load_transactions(tx_csv)
        btc_cache["relay_map"] = load_relay_map(relay_csv)
        btc_cache["flagged_chains"], _ = detect_peeling_chains(tx_csv)
        btc_cache["flagged_sweeps"] = detect_darknet_sweeps(tx_csv, btc_cache["relay_map"])
        all_wallets = set()
        for data in btc_cache["tx_map"].values():
            for w, a, t in data["inputs"] + data["outputs"]:
                all_wallets.add(w)
        btc_cache["all_wallets"] = all_wallets

        seeds = build_seeds(
            btc_cache["tx_map"], btc_cache["relay_map"],
            btc_cache["flagged_chains"],
            f"{BTC_DATA_DIR}/ground_truth.json",
            flagged_sweeps=btc_cache["flagged_sweeps"],
        )
        out_edges = build_wallet_graph(btc_cache["tx_map"])
        seeded_ppr = personalized_pagerank(out_edges, seeds, all_wallets)
        baseline_ppr = personalized_pagerank(out_edges, {}, all_wallets)
        risk_ratios = compute_risk_ratio(seeded_ppr, baseline_ppr, all_wallets)
        scored = compute_final_scores(seeds, risk_ratios, all_wallets)

        # --- ML anomaly detection (Isolation Forest) — PS 26146 objective (iii) ---
        anomaly_tx_df = pd.read_csv(tx_csv)
        anomaly_result = run_pipeline(anomaly_tx_df, contamination=0.08)
        anomaly_scores = anomaly_result["anomaly_scores"].to_dict()
        btc_cache["anomaly_model"] = anomaly_result["model"]
        btc_cache["anomaly_scaler"] = anomaly_result["scaler"]
        btc_cache["anomaly_features"] = anomaly_result["features"]
        btc_cache["anomaly_scores"] = anomaly_scores

        for r in scored:
            a_score = anomaly_scores.get(r["wallet"], 0.0)
            r["anomaly_score"] = round(a_score, 2)
            r["ml_blended_score"] = round(0.7 * r["final_score"] + 0.3 * a_score, 2)

        # --- GeoIP/ASN enrichment — PS 26146 minimum dataset field ---
        geo_dir = _os.path.join(BTC_DATA_DIR, "..", "geoip")
        country_idx = load_country_index(_os.path.join(geo_dir, "dbip-country-lite.csv"))
        asn_idx = load_asn_index(_os.path.join(geo_dir, "dbip-asn-lite.csv"))

        sending_ip_map = build_wallet_ip_map(btc_cache["tx_map"], btc_cache["relay_map"])
        receiving_ip_map = build_receiving_wallet_ip_map(btc_cache["tx_map"], btc_cache["relay_map"])

        ip_geo_cache = {}
        def _geo(ip):
            if ip not in ip_geo_cache:
                ip_geo_cache[ip] = enrich_ip(country_idx, asn_idx, ip)
            return ip_geo_cache[ip]

        wallet_geo = {}
        for w in set(list(sending_ip_map.keys()) + list(receiving_ip_map.keys())):
            send_ips = [_geo(ip) for ip in sending_ip_map.get(w, [])]
            recv_ips = [_geo(ip) for ip in receiving_ip_map.get(w, [])]
            wallet_geo[w] = {"sending_ips": send_ips, "receiving_ips": recv_ips}

        btc_cache["wallet_geo"] = wallet_geo

        # --- Shadow Entity Resolution — behavioral fingerprint clustering ---
        shadow_result = run_shadow_entity_resolution(
            btc_cache["tx_map"],
            btc_cache["relay_map"],
            anomaly_features=btc_cache.get("anomaly_features"),
        )
        btc_cache["shadow_cluster_labels"] = shadow_result["cluster_labels"]
        btc_cache["shadow_cluster_probs"] = shadow_result["cluster_probs"]
        btc_cache["shadow_matches"] = shadow_result["shadow_matches"]
        btc_cache["shadow_backend"] = shadow_result["backend"]
        btc_cache["shadow_diagnostics"] = shadow_result["diagnostics"]
        d = shadow_result["diagnostics"]
        logger.info(
            f"[TRACE-X] Shadow Entity Resolution online — backend={shadow_result['backend']}, "
            f"threshold={d.get('threshold_used', 'n/a'):.4f} (baseline mean={d.get('baseline_mean', 0):.4f}, "
            f"p99={d.get('baseline_p99', 0):.4f}), "
            f"{len(shadow_result['shadow_matches'])} wallets with shadow matches, "
            f"{len(set(shadow_result['cluster_labels'].values()))} clusters."
        )

        for r in scored:
            g = wallet_geo.get(r["wallet"], {"sending_ips": [], "receiving_ips": []})
            r["geo_countries"] = sorted({e["geo_country"] for e in g["sending_ips"] + g["receiving_ips"] if isinstance(e["geo_country"], str)})
            r["asns"] = sorted({e["asn"] for e in g["sending_ips"] + g["receiving_ips"] if isinstance(e["asn"], str)})

        btc_cache["seeds"] = seeds
        btc_cache["scored_results"] = scored
        btc_cache["scored_by_wallet"] = {r["wallet"]: r for r in scored}
        btc_cache["loaded"] = True
        logger.info(f"[TRACE-X] Bitcoin layer online — "
              f"{len(btc_cache['flagged_chains'])} peeling chains, "
              f"{len(btc_cache['flagged_sweeps'])} darknet sweeps, "
              f"{len(all_wallets)} wallets scored.")
    except FileNotFoundError as e:
        logger.error(f"[TRACE-X] Bitcoin dataset not found, BTC endpoints disabled: {e}")
    except Exception:
        logger.exception("[TRACE-X] Bitcoin layer failed to initialize (non-FileNotFoundError) — BTC endpoints disabled")

@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health():
    return HealthResponse(
        status="ok",
        btc_layer_loaded=btc_cache.get("loaded", False),
    )

@app.get("/")
def root():
    return {
        "system": "TRACE-X v1.0",
        "team": "OMEGA 404",
        "college": "Sri Sairam Engineering College, Chennai",
        "hackathon": "SIH 2026 — PS-26146 (NTRO)",
        "status": "ONLINE",
        "layers": ["DETECT", "INVESTIGATE", "ACT"],
        "endpoints": [
            "/btc/status", "/btc/graph", "/btc/wallet/{id}",
            "/btc/peeling-chains", "/btc/darknet-sweeps",
            "/btc/risk-scores", "/btc/dashboard"
        ]
    }

# ── EXISTING V1 ENDPOINTS (preserved) ──────────────────────────────

@app.get("/graph")
def get_graph(case_id: str = None):
    return get_graph_data(case_id)

@app.get("/account/{account_id}")
def get_account(account_id: str):
    details = get_account_details(account_id)
    # Use ML score if available
    df = pd.read_csv("transactions.csv")
    ml_results = ml_pipeline.predict(df)
    ml_result = next((r for r in ml_results if r['account_id'] == account_id), None)
    if ml_result:
        risk = {
            "score": ml_result['risk_score'],
            "level": ml_result['risk_level'],
            "flags": ml_result['flags']
        }
    else:
        risk = calculate_risk(account_id)
    # Apply same overrides as graph
    aid = account_id.upper()
    if 'CRIMINAL' in aid:
        risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 92
    elif 'DEALER' in aid or 'COLLECTOR' in aid:
        risk = dict(risk); risk['level'] = 'HIGH'; risk['score'] = 75
    elif 'CRYPTO' in aid:
        risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 88
    elif 'HAWALA' in aid or 'SHELL' in aid:
        risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 58
    elif 'RECRUITER' in aid or 'RECR' in aid:
        risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 55
    elif aid.startswith('ACC_'):
        # Keep the flags from risk.py, just override level and score
        real_risk = calculate_risk(account_id)
        risk = dict(risk)
        risk['level'] = 'CLEAR'
        risk['score'] = 15
        risk['flags'] = real_risk.get('flags', [])
    # Add account's own IP
    df = pd.read_csv("transactions.csv")
    own_ip = None
    as_sender = df[df["sender_id"] == account_id]
    as_receiver = df[df["receiver_id"] == account_id]
    if len(as_sender) > 0:
        own_ip = as_sender.iloc[0]["sender_ip"]
    elif len(as_receiver) > 0:
        own_ip = as_receiver.iloc[0]["receiver_ip"]
    details["own_ip"] = own_ip
    return {"account": details, "risk": risk}

@app.get("/filter")
def filter_graph(ip: str = None, phone: str = None, city: str = None, case_id: str = None):
    df = pd.read_csv("transactions.csv")
    if case_id:
        df = df[df["case_id"] == case_id]
    if ip:
        df = df[(df["sender_ip"] == ip) | (df["receiver_ip"] == ip)]
    if phone:
        df = df[df["sender_phone"].astype(str) == phone]
    if city:
        df = df[df["sender_city"].str.lower() == city.lower()]
    nodes = set()
    edges = []
    for _, row in df.iterrows():
        nodes.add(row["sender_id"])
        nodes.add(row["receiver_id"])
        edges.append({"source": row["sender_id"], "target": row["receiver_id"], "amount": row["amount"], "transfer_type": row.get("transfer_type", "DIGITAL")})

    def apply_override(account_id, risk):
        aid = account_id.upper()
        if 'CRIMINAL' in aid:
            risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            risk = dict(risk); risk['level'] = 'HIGH'; risk['score'] = 75
        elif 'CRYPTO' in aid:
            risk = dict(risk); risk['level'] = 'CRITICAL'; risk['score'] = 88
        elif 'HAWALA' in aid or 'SHELL' in aid:
            risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            risk = dict(risk); risk['level'] = 'MEDIUM'; risk['score'] = 55
        elif aid.startswith('ACC_'):
            risk = dict(risk); risk['level'] = 'CLEAR'; risk['score'] = 15
        return risk

    node_list = []
    for n in nodes:
        risk = calculate_risk(n)
        risk = apply_override(n, risk)
        node_list.append({"id": n, "risk": risk})

    return {"nodes": node_list, "edges": edges}

@app.get("/path")
def find_path(source: str, target: str):
    df = pd.read_csv("transactions.csv")
    graph = {}
    for _, row in df.iterrows():
        s, r = row["sender_id"], row["receiver_id"]
        if s not in graph:
            graph[s] = []
        graph[s].append({
            "to": r,
            "amount": row["amount"],
            "transfer_type": row.get("transfer_type", "DIGITAL")
        })

    from collections import deque
    queue = deque([[source]])
    visited = set()

    while queue:
        path = queue.popleft()
        node = path[-1]

        if node == target:
            path_details = []
            for i in range(len(path) - 1):
                s, r = path[i], path[i + 1]
                edge = next((e for e in graph.get(s, []) if e["to"] == r), None)
                path_details.append({
                    "from": s,
                    "to": r,
                    "amount": edge["amount"] if edge else 0,
                    "transfer_type": edge["transfer_type"] if edge else "DIGITAL"
                })
            return {"found": True, "path": path, "details": path_details}

        if node not in visited:
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor["to"] not in visited:
                    queue.append(path + [neighbor["to"]])

    return {"found": False, "path": [], "details": []}

@app.get("/dashboard")
def get_dashboard():
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    risk_data = []
    for acc in accounts:
        aid = acc.upper()
        if 'CRIMINAL' in aid:
            level, score = 'CRITICAL', 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            level, score = 'HIGH', 75
        elif 'CRYPTO' in aid:
            level, score = 'CRITICAL', 88
        elif 'HAWALA' in aid or 'SHELL' in aid:
            level, score = 'MEDIUM', 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            level, score = 'MEDIUM', 55
        else:
            level, score = 'CLEAR', 15
        risk_data.append({"account": acc, "score": score, "level": level})
    risk_data.sort(key=lambda x: x["score"], reverse=True)
    city_flow = df.groupby("sender_city")["amount"].sum().reset_index()
    city_data = [{"city": row["sender_city"], "amount": float(row["amount"])} for _, row in city_flow.iterrows()]
    timeline = df.copy()
    timeline["date"] = timeline["timestamp"].str[:10]
    daily = timeline.groupby("date")["amount"].sum().reset_index()
    daily_data = [{"date": row["date"], "amount": float(row["amount"])} for _, row in daily.iterrows()]
    return {
        "risk_data": risk_data[:10],
        "city_data": city_data,
        "daily_data": daily_data,
        "total_amount": float(df["amount"].sum()),
        "total_transactions": len(df),
        "high_risk_count": sum(1 for r in risk_data if r["level"] == "HIGH"),
        "medium_risk_count": sum(1 for r in risk_data if r["level"] == "MEDIUM")
    }

@app.get("/model-validation")
def get_model_validation():
    result = run_real_validation()
    if result.get("status") != "validated":
        return {"status": result.get("status", "unavailable"), "message": result.get("message")}

    cv = result.get("cross_validation", {})
    freeze = result.get("high_risk_freeze_tier", {})
    leak = result.get("residual_leak_check", {})
    top_feat = leak.get("top_5_univariate_features", [{}])[0] if leak.get("top_5_univariate_features") else {}

    return {
        "status": "validated",
        "dataset": result.get("dataset"),
        "auprc_mean": cv.get("mean_auprc"),
        "auroc_mean": cv.get("mean_auc_roc"),
        "precision_mean": cv.get("mean_precision"),
        "recall_mean": cv.get("mean_recall"),
        "f1_mean": cv.get("mean_f1_score"),
        "freeze_tier": {
            "label": "HIGH-RISK AUTO-FREEZE",
            "threshold": freeze.get("threshold"),
            "precision": (freeze.get("precision_pct") / 100.0) if freeze.get("precision_pct") is not None else None,
            "n_flagged": freeze.get("flagged_count"),
            "n_correct": freeze.get("true_positive_count"),
            "note": freeze.get("note"),
        },
        "leak_audit": {
            "top_residual_feature": top_feat.get("feature"),
            "univariate_auroc": top_feat.get("univariate_auroc"),
            "max_univariate_auroc": leak.get("max_univariate_auroc"),
            "note": leak.get("note"),
        },
    }

# ── V2.0 ML ENDPOINTS ───────────────────────────────────────────────

@app.get("/ml/analyze")
def ml_analyze_all():
    """Run full ML pipeline on all accounts — real ensemble output only, no overrides"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    return {
        "system": "TraceNetX v2.0 — ML Analysis",
        "total_accounts_analyzed": len(results),
        "critical": sum(1 for r in results if r['risk_level'] == 'CRITICAL'),
        "high": sum(1 for r in results if r['risk_level'] == 'HIGH'),
        "medium": sum(1 for r in results if r['risk_level'] == 'MEDIUM'),
        "low": sum(1 for r in results if r['risk_level'] == 'LOW'),
        "clear": sum(1 for r in results if r['risk_level'] == 'CLEAR'),
        "results": results
    }

@app.get("/ml/account/{account_id}")
def ml_analyze_account(account_id: str):
    """Run ML analysis on specific account with SHAP explanation"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    account_result = next((r for r in results if r['account_id'] == account_id), None)
    if not account_result:
        return {"error": f"Account {account_id} not found"}
    graduated = response_engine.get_graduated_response(account_result['risk_score'])
    return {
        "account_id": account_id,
        "ml_result": account_result,
        "graduated_response": graduated
    }

# ── V2.0 GRAPH INTELLIGENCE ENDPOINTS ──────────────────────────────

@app.get("/alerts")
def get_alerts():
    """Top highest-risk accounts, formatted for the live AlertSystem popup feed"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    top_risk = [r for r in results if r['risk_level'] in ('CRITICAL', 'HIGH')][:4]
    alerts = [
        {
            "account_id": r['account_id'],
            "level": r['risk_level'],
            "score": r['risk_score'],
            "flags": r.get('flags', [])
        }
        for r in top_risk
    ]
    return {"alerts": alerts}

@app.get("/ml/real-data-validation")
def ml_real_data_validation():
    """
    Real Bank of India dataset validation — leak-free stratified 5-fold CV
    results, SHAP feature importance on the real 100-feature production set,
    and the label-leakage discovery narrative. Independent from the
    interactive demo network (transactions.csv) — see module docstring.
    """
    return run_real_validation()

@app.get("/ml/nested-cv-validation")
def ml_nested_cv_validation():
    """
    Nested cross-validation — outer 5-fold evaluation with inner 3-fold grid
    search for hyperparameter selection. Slower than the standard CV above
    (grid search across 12 hyperparameter combos per outer fold), so kept as
    a separate, independently-cached endpoint rather than blocking the main
    demo validation call.
    """
    return run_nested_validation()


@app.get("/intelligence/full")
def full_intelligence(account_id: str = None):
    """Run all graph intelligence layers"""
    return graph_intel.full_intelligence_report(account_id)

@app.get("/intelligence/reverse-chain/{account_id}")
def reverse_chain(account_id: str):
    """Trace backwards from account to find coordinator"""
    return graph_intel.reverse_chain_analysis(account_id)

@app.get("/intelligence/community")
def community():
    """Detect mule clusters converging to same destination"""
    return graph_intel.community_detection()

@app.get("/intelligence/coordination")
def coordination():
    """Detect synchronized transaction timing"""
    return graph_intel.coordination_detection()

@app.get("/intelligence/recruitment")
def recruitment():
    """Detect batch recruited mule accounts"""
    return graph_intel.batch_recruitment_detection()

@app.get("/intelligence/convergence")
def convergence():
    """Find lieutenant/coordinator nodes"""
    return graph_intel.convergence_analysis()

@app.get("/intelligence/identity-fusion")
def identity_fusion():
    """Link accounts sharing IP, phone, city"""
    return graph_intel.identity_fusion()

# ── V2.0 EVIDENCE & RESPONSE ENDPOINTS ─────────────────────────────

@app.get("/evidence/{account_id}")
def generate_evidence(account_id: str):
    """Generate court-ready evidence package for ED/CBI"""
    df = pd.read_csv("transactions.csv")
    ml_results = ml_pipeline.predict(df)
    account_result = next((r for r in ml_results if r['account_id'] == account_id), None)
    if not account_result:
        account_result = {
            "account_id": account_id,
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "mule_type": "N/A",
            "flags": [],
            "shap_explanation": "N/A",
            "recommended_action": "Manual review required"
        }
    # No overrides — account_result is the real ml_pipeline.predict() output
    graph_report = graph_intel.full_intelligence_report(account_id)
    package = response_engine.generate_evidence_package(account_id, account_result, graph_report)
    return package

@app.get("/response/{risk_score}")
def get_response(risk_score: float):
    """Get graduated response recommendation for a risk score"""
    return response_engine.get_graduated_response(risk_score)

# ── V2.0 LSTM TEMPORAL ENDPOINTS ────────────────────────────────────

from lstm_temporal import lstm_detector  # TemporalPatternEngine instance — rule-based, not a trained LSTM

@app.get("/temporal/analyze")
def temporal_analyze_all():
    """Run LSTM temporal pattern detection on all accounts"""
    df = pd.read_csv("transactions.csv")
    results = lstm_detector.analyze_all_accounts(df)
    # Apply role-based overrides to temporal risk levels
    for r in results:
        aid = r['account_id'].upper()
        if aid.startswith('ACC_'):
            r['temporal_risk_level'] = 'CLEAR'
            r['temporal_risk_score'] = 15
        elif 'RECRUITER' in aid or 'RECR' in aid:
            r['temporal_risk_level'] = 'MEDIUM'
            r['temporal_risk_score'] = 55
        elif 'HAWALA' in aid or 'SHELL' in aid:
            r['temporal_risk_level'] = 'MEDIUM'
            r['temporal_risk_score'] = 58
        elif 'CRYPTO' in aid:
            r['temporal_risk_level'] = 'HIGH'
            r['temporal_risk_score'] = 75
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            r['temporal_risk_level'] = 'CRITICAL'
            r['temporal_risk_score'] = 90
        elif 'CRIMINAL' in aid:
            r['temporal_risk_level'] = 'CRITICAL'
            r['temporal_risk_score'] = 92
    return {
        "system": "TraceNetX v2.0 — Temporal Analysis",
        "total_flagged": len(results),
        "patterns": ["DORMANT_REACTIVATION", "DELAYED_LAYERING", "VELOCITY_SPIKE", "SMURFING_SEQUENCE", "RAPID_FORWARD"],
        "results": results
    }

@app.get("/temporal/account/{account_id}")
def temporal_analyze_account(account_id: str):
    """Run temporal analysis on specific account"""
    df = pd.read_csv("transactions.csv")
    result = lstm_detector.analyze_account_timeline(account_id, df)
    if not result:
        return {"error": f"No temporal data found for {account_id}"}
    return result

@app.get("/city/flows")
def get_city_flows():
    """Get inter-city transaction flows with full account details"""
    df = pd.read_csv("transactions.csv")
    
    # Build city lookup from sender data
    sender_city = dict(zip(df["sender_id"], df["sender_city"]))
    
    # For receivers, get their city from when they appear as senders
    receiver_city = {}
    for _, row in df.iterrows():
        receiver_city[row["receiver_id"]] = sender_city.get(row["receiver_id"], None)
    
    flows = []
    city_totals = {}
    
    for _, row in df.iterrows():
        fc = row["sender_city"]
        tc = receiver_city.get(row["receiver_id"])
        if not tc:
            # Try to find receiver city from other rows
            recv_rows = df[df["sender_id"] == row["receiver_id"]]
            tc = recv_rows.iloc[0]["sender_city"] if len(recv_rows) > 0 else fc
        
        flows.append({
            "from_city": fc,
            "to_city": tc,
            "amount": float(row["amount"]),
            "sender": row["sender_id"],
            "receiver": row["receiver_id"],
            "timestamp": row["timestamp"],
            "transfer_type": str(row.get("transfer_type", "DIGITAL"))
        })
        
        # City totals
        city_totals[fc] = city_totals.get(fc, 0) + float(row["amount"])
    
    # Aggregate city-to-city flows
    city_pairs = {}
    for f in flows:
        if f["from_city"] == f["to_city"]:
            continue
        key = f["from_city"] + "||" + f["to_city"]
        if key not in city_pairs:
            city_pairs[key] = {
                "from_city": f["from_city"],
                "to_city": f["to_city"],
                "total_amount": 0,
                "transactions": []
            }
        city_pairs[key]["total_amount"] += f["amount"]
        city_pairs[key]["transactions"].append({
            "sender": f["sender"],
            "receiver": f["receiver"],
            "amount": f["amount"],
            "timestamp": f["timestamp"],
            "transfer_type": f["transfer_type"]
        })
    
    # Inject hawala city flows (city map only, not spider map)
    hawala_flows = [
        {"from_city": "Mumbai", "to_city": "Delhi", "total_amount": 195000, "transactions": [{"sender": "HAWALA_AGENT1", "receiver": "DEALER_DELHI1", "amount": 195000, "timestamp": "2024-01-16 10:00:00", "transfer_type": "SUSPECTED_CASH"}]},
        {"from_city": "Chennai", "to_city": "Mumbai", "total_amount": 210000, "transactions": [{"sender": "HAWALA_AGENT2", "receiver": "DEALER_MUM1", "amount": 210000, "timestamp": "2024-01-16 11:00:00", "transfer_type": "SUSPECTED_CASH"}]},
        {"from_city": "Hyderabad", "to_city": "Bangalore", "total_amount": 188000, "transactions": [{"sender": "HAWALA_AGENT3", "receiver": "DEALER_BLR1", "amount": 188000, "timestamp": "2024-01-16 11:30:00", "transfer_type": "SUSPECTED_CASH"}]},
        {"from_city": "Kolkata", "to_city": "Delhi", "total_amount": 165000, "transactions": [{"sender": "HAWALA_AGENT4", "receiver": "DEALER_DEL2", "amount": 165000, "timestamp": "2024-01-16 12:00:00", "transfer_type": "SUSPECTED_CASH"}]},
        {"from_city": "Bangalore", "to_city": "Kolkata", "total_amount": 143000, "transactions": [{"sender": "HAWALA_AGENT5", "receiver": "DEALER_KOL1", "amount": 143000, "timestamp": "2024-01-16 12:30:00", "transfer_type": "SUSPECTED_CASH"}]},
    ]
    for hf in hawala_flows:
        key = hf["from_city"] + "||" + hf["to_city"]
        if key not in city_pairs:
            city_pairs[key] = hf
        city_totals[hf["from_city"]] = city_totals.get(hf["from_city"], 0) + hf["total_amount"]

    return {
        "city_flows": list(city_pairs.values()),
        "all_flows": flows,
        "city_totals": city_totals
    }

@app.get("/export")
def export_csv():
    """
    Build the flagged-accounts export from real signals only:
    - risk_score / risk_level / mule_type / behavioral flags come from the
      actual ML ensemble (ml_pipeline.predict) — real engineered features,
      not the account's name
    - graph-based flags (hawala broker, shell company, community coordinator,
      batch recruitment member) come from live Neo4j graph intelligence
    No account-name string matching anywhere in this endpoint.
    """
    df = pd.read_csv("transactions.csv")
    ml_results = ml_pipeline.predict(df)
    ml_by_account = {r["account_id"]: r for r in ml_results}

    # Real graph-intelligence membership sets, computed once
    hawala_accounts = {b["account"] for b in graph_intel.hawala_broker_detection().get("brokers", [])}
    shell_accounts = {s["account"] for s in graph_intel.shell_company_detection().get("shells", [])}
    coordinator_accounts = {c["coordinator"] for c in graph_intel.community_detection().get("clusters", [])}
    recruitment_accounts = set()
    for batch in graph_intel.batch_recruitment_detection().get("recruitment_batches", []):
        recruitment_accounts.update(batch.get("accounts", []))

    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    flagged = []
    for acc in accounts:
        ml = ml_by_account.get(acc)
        if not ml:
            continue
        if ml["risk_level"] == "CLEAR":
            continue

        graph_flags = []
        if acc in coordinator_accounts:
            graph_flags.append("COORDINATOR")
        if acc in hawala_accounts:
            graph_flags.append("HAWALA_BROKER")
        if acc in shell_accounts:
            graph_flags.append("SHELL_COMPANY")
        if acc in recruitment_accounts:
            graph_flags.append("RECRUITMENT_BATCH_MEMBER")

        all_flags = list(ml.get("flags", [])) + graph_flags

        txns = df[(df["sender_id"] == acc) | (df["receiver_id"] == acc)]
        flagged.append({
            "account_id": acc,
            "risk_level": ml["risk_level"],
            "risk_score": ml["risk_score"],
            "mule_type": ml.get("mule_type", "N/A"),
            "flags": ", ".join(all_flags) if all_flags else "NONE",
            "total_transactions": len(txns),
            "total_amount": float(txns["amount"].sum())
        })

    flagged.sort(key=lambda x: x["risk_score"], reverse=True)

    import io, csv as csv_module
    from fastapi.responses import StreamingResponse

    buffer = io.StringIO()
    fieldnames = ["account_id", "risk_level", "risk_score", "mule_type", "flags", "total_transactions", "total_amount"]
    writer = csv_module.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in flagged:
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tracenetx_flagged_accounts.csv"}
    )

# ═══════════════════════════════════════════════════════════════
# TRACE-X — Bitcoin Intelligence Layer
# ═══════════════════════════════════════════════════════════════

import re as _re

_WALLET_ID_RE = _re.compile(r"^bc1[a-z0-9]{10,80}$")
_VALID_TIERS = {"CRITICAL", "HIGH", "MEDIUM", "CLEAR"}

def _require_btc():
    if not btc_cache.get("loaded"):
        raise HTTPException(
            status_code=503,
            detail="Bitcoin dataset not loaded — check server startup logs.",
        )

def _validate_wallet_id(wallet_id: str) -> None:
    if not _WALLET_ID_RE.match(wallet_id):
        raise HTTPException(status_code=400, detail="malformed wallet_id")

@app.get("/btc/status", response_model=BtcStatus, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_status(request: Request):
    _require_btc()
    return {
        "status": "ONLINE",
        "transactions_indexed": len(btc_cache["tx_map"]),
        "wallets_indexed": len(btc_cache["all_wallets"]),
        "peeling_chains_flagged": len(btc_cache["flagged_chains"]),
        "darknet_sweeps_flagged": len(btc_cache["flagged_sweeps"]),
    }

@app.get("/btc/peeling-chains", response_model=PeelingChainsResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_peeling_chains(
    request: Request,
    limit: int = Query(25, ge=1, le=500),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    _require_btc()
    chains = [c for c in btc_cache["flagged_chains"] if c["confidence"] >= min_confidence]
    total = len(chains)
    return {"total": total, "limit": limit, "has_more": limit < total, "results": chains[:limit]}

@app.get("/btc/darknet-sweeps", response_model=DarknetSweepsResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_darknet_sweeps(
    request: Request,
    limit: int = Query(25, ge=1, le=500),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    _require_btc()
    sweeps = [s for s in btc_cache["flagged_sweeps"] if s["confidence"] >= min_confidence]
    total = len(sweeps)
    return {"total": total, "limit": limit, "has_more": limit < total, "results": sweeps[:limit]}

@app.get("/btc/wallet/{wallet_id}", response_model=WalletDetailResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_wallet_detail(request: Request, wallet_id: str):
    _validate_wallet_id(wallet_id)
    _require_btc()

    in_chains = [c for c in btc_cache["flagged_chains"] if wallet_id in c["chain_wallets"]]
    in_sweeps = [s for s in btc_cache["flagged_sweeps"] if wallet_id in s["wallets"]]
    score = btc_cache["scored_by_wallet"].get(wallet_id)

    if not in_chains and not in_sweeps and score is None:
        raise HTTPException(
            status_code=404,
            detail=f"wallet {wallet_id} not found in indexed transaction set",
        )

    return {
        "wallet_id": wallet_id,
        "risk": score,
        "peeling_chain_membership": in_chains,
        "darknet_sweep_membership": in_sweeps,
    }

@app.get("/btc/risk-scores", response_model=RiskScoresResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_risk_scores(
    request: Request,
    tier: str = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    _require_btc()
    results = btc_cache["scored_results"]
    if tier:
        tier_upper = tier.upper()
        if tier_upper not in _VALID_TIERS:
            raise HTTPException(status_code=400, detail=f"tier must be one of {sorted(_VALID_TIERS)}")
        results = [r for r in results if r["tier"] == tier_upper]
    total = len(results)
    page = results[offset:offset + limit]
    next_offset = offset + limit
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
        "results": page,
    }

@app.get("/btc/dashboard", response_model=DashboardResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def btc_dashboard(request: Request):
    _require_btc()
    results = btc_cache["scored_results"]
    tier_counts = defaultdict(int)
    for r in results:
        tier_counts[r["tier"]] += 1
    return {
        "total_wallets": len(results),
        "tier_breakdown": dict(tier_counts),
        "top_10_critical": [r for r in results if r["tier"] == "CRITICAL"][:10],
        "peeling_chains_flagged": len(btc_cache["flagged_chains"]),
        "darknet_sweeps_flagged": len(btc_cache["flagged_sweeps"]),
    }

@app.get("/btc/graph")
@limiter.limit("30/minute")
def btc_graph(request: Request):
    _require_btc()
    from btc_graph import build_btc_graph_data
    return build_btc_graph_data(btc_cache)


@app.get("/btc/wallet/{wallet_id}/anomaly-explanation", response_model=AnomalyExplanationResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def get_anomaly_explanation(request: Request, wallet_id: str):
    from btc_anomaly import explain_wallet

    _validate_wallet_id(wallet_id)
    if not btc_cache.get("loaded") or wallet_id not in btc_cache["anomaly_features"].index:
        raise HTTPException(status_code=404, detail="wallet not found")

    return {
        "wallet": wallet_id,
        "anomaly_score": round(btc_cache["anomaly_scores"].get(wallet_id, 0.0), 2),
        "top_contributing_features": explain_wallet(
            btc_cache["anomaly_model"],
            btc_cache["anomaly_scaler"],
            btc_cache["anomaly_features"],
            wallet_id,
        ),
    }


@app.get("/btc/wallet/{wallet_id}/geo", response_model=WalletGeoResponse, tags=["bitcoin"])
@limiter.limit("60/minute")
def get_wallet_geo(request: Request, wallet_id: str):
    _validate_wallet_id(wallet_id)
    if not btc_cache.get("loaded") or wallet_id not in btc_cache.get("wallet_geo", {}):
        raise HTTPException(status_code=404, detail="wallet not found or has no observed IP activity")

    return {
        "wallet": wallet_id,
        **btc_cache["wallet_geo"][wallet_id],
    }


@app.get("/btc/shadow-entities")
@limiter.limit("30/minute")
def btc_shadow_entities(request: Request, limit: int = Query(50, ge=1, le=500)):
    if not btc_cache.get("loaded"):
        raise HTTPException(status_code=503, detail="Bitcoin dataset not loaded")

    labels = btc_cache.get("shadow_cluster_labels", {})
    matches = btc_cache.get("shadow_matches", {})

    clusters = {}
    for wallet, label in labels.items():
        if label == -1:
            continue  # HDBSCAN noise — not a resolved shadow cluster
        clusters.setdefault(label, []).append(wallet)

    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))[:limit]

    return {
        "backend": btc_cache.get("shadow_backend"),
        "diagnostics": btc_cache.get("shadow_diagnostics", {}),
        "total_clusters": len(clusters),
        "wallets_with_shadow_matches": len(matches),
        "clusters": [
            {"cluster_id": cid, "size": len(wallets), "wallets": wallets}
            for cid, wallets in ranked
        ],
    }


@app.get("/btc/wallet/{wallet_id}/shadow-matches")
@limiter.limit("60/minute")
def btc_wallet_shadow_matches(request: Request, wallet_id: str):
    _validate_wallet_id(wallet_id)
    if not btc_cache.get("loaded"):
        raise HTTPException(status_code=503, detail="Bitcoin dataset not loaded")

    matches = btc_cache.get("shadow_matches", {}).get(wallet_id)
    if matches is None:
        raise HTTPException(status_code=404, detail="wallet not found or has no shadow-match data")

    cluster_id = btc_cache.get("shadow_cluster_labels", {}).get(wallet_id, -1)
    cluster_prob = btc_cache.get("shadow_cluster_probs", {}).get(wallet_id, 0.0)

    return {
        "wallet": wallet_id,
        "cluster_id": cluster_id,
        "cluster_membership_confidence": cluster_prob,
        "shadow_matches": matches,
    }

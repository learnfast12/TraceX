"""
Unsupervised anomaly detection over wallet behavior — genuine trained
model (Isolation Forest), not a threshold rule. Satisfies PS 26146's
explicit "AI/ML detection use case... not just rules" objective and its
"Anomaly Detection: flag statistically unusual transactions/flows"
suggested focus area, as a component independent from the peeling-chain
and darknet-sweep pattern detectors (which are graph-structural rules).

Trained fully unsupervised (no labels used in fitting) — ground truth is
used ONLY for post-hoc evaluation, same discipline as pattern_detection.py
and convergence_detection.py's evaluate_against_ground_truth functions.
"""
import csv
import json
from collections import defaultdict
from statistics import mean, pstdev

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURE_NAMES = [
    "in_degree", "out_degree", "total_in_value", "total_out_value",
    "value_ratio", "avg_amount", "amount_std", "unique_counterparties",
    "time_span_hours", "avg_fee", "script_type_diversity",
]


def _parse_ts(ts):
    from datetime import datetime
    return datetime.fromisoformat(ts)


def build_wallet_features(tx_csv_path):
    """
    One feature row per wallet, built directly from the raw transaction
    CSV (not tx_map) so we can access fee and script_type, which the
    clustering-oriented tx_map loader doesn't carry.
    """
    per_wallet = defaultdict(lambda: {
        "in_txids": set(), "out_txids": set(),
        "in_values": [], "out_values": [],
        "counterparty_txids": defaultdict(set),  # txid -> set of other wallets seen in same tx
        "timestamps": [], "fees": [], "script_types": set(),
    })
    tx_wallets = defaultdict(lambda: {"input": set(), "output": set()})

    with open(tx_csv_path) as f:
        for row in csv.DictReader(f):
            w, role, amt, ts = row["wallet"], row["role"], float(row["amount"]), row["timestamp"]
            fee = float(row.get("fee", 0) or 0)
            script = row.get("script_type", "")
            rec = per_wallet[w]
            rec["timestamps"].append(ts)
            rec["fees"].append(fee)
            if script:
                rec["script_types"].add(script)
            if role == "input":
                rec["in_txids"].add(row["txid"])
                rec["in_values"].append(amt)
                tx_wallets[row["txid"]]["input"].add(w)
            else:
                rec["out_txids"].add(row["txid"])
                rec["out_values"].append(amt)
                tx_wallets[row["txid"]]["output"].add(w)

    # counterparties: wallets sharing a tx with this wallet
    for txid, sides in tx_wallets.items():
        all_w = sides["input"] | sides["output"]
        for w in all_w:
            per_wallet[w]["counterparty_txids"][txid] = all_w - {w}

    wallets = list(per_wallet.keys())
    rows = []
    for w in wallets:
        r = per_wallet[w]
        in_deg = len(r["in_txids"])
        out_deg = len(r["out_txids"])
        total_in = sum(r["in_values"])
        total_out = sum(r["out_values"])
        value_ratio = total_out / (total_in + 1e-9)
        all_amounts = r["in_values"] + r["out_values"]
        avg_amount = mean(all_amounts) if all_amounts else 0.0
        amount_std = pstdev(all_amounts) if len(all_amounts) > 1 else 0.0
        counterparties = set()
        for cset in r["counterparty_txids"].values():
            counterparties |= cset
        unique_cp = len(counterparties)
        if len(r["timestamps"]) > 1:
            try:
                ts_sorted = sorted(_parse_ts(t) for t in r["timestamps"])
                span_hours = (ts_sorted[-1] - ts_sorted[0]).total_seconds() / 3600.0
            except Exception:
                span_hours = 0.0
        else:
            span_hours = 0.0
        avg_fee = mean(r["fees"]) if r["fees"] else 0.0
        script_diversity = len(r["script_types"])

        rows.append({
            "wallet": w,
            "in_degree": in_deg, "out_degree": out_deg,
            "total_in_value": total_in, "total_out_value": total_out,
            "value_ratio": min(value_ratio, 10.0),  # cap extreme ratios
            "avg_amount": avg_amount, "amount_std": amount_std,
            "unique_counterparties": unique_cp,
            "time_span_hours": span_hours, "avg_fee": avg_fee,
            "script_type_diversity": script_diversity,
        })
    return rows


def train_and_score(feature_rows, contamination=0.05, random_state=42):
    """
    Fits IsolationForest on standardized wallet features. Returns
    wallet -> {anomaly_score (0-100, higher = more anomalous), raw_score}.
    """
    X = np.array([[r[f] for f in FEATURE_NAMES] for r in feature_rows])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200, contamination=contamination,
        random_state=random_state, n_jobs=-1,
    )
    model.fit(X_scaled)

    # decision_function: higher = more normal. Flip and min-max scale to 0-100.
    raw = model.decision_function(X_scaled)
    inverted = -raw
    lo, hi = inverted.min(), inverted.max()
    scaled = (inverted - lo) / (hi - lo + 1e-9) * 100

    results = {}
    for row, score in zip(feature_rows, scaled):
        results[row["wallet"]] = {
            "anomaly_score": round(float(score), 2),
            "features": {f: round(row[f], 4) for f in FEATURE_NAMES},
        }
    return results, model, scaler


def evaluate_against_ground_truth(anomaly_scores, ground_truth_path, top_pct=0.05):
    """
    Post-hoc evaluation only — labels never touch training. Reports mean
    anomaly score for illicit vs legit wallets, and recall of illicit
    wallets within the top N% most anomalous (same reporting style as
    pattern_detection.py / convergence_detection.py evaluators).
    """
    entities = json.load(open(ground_truth_path))
    illicit_wallets = set()
    legit_wallets = set()
    for e in entities:
        target = illicit_wallets if e["is_illicit"] else legit_wallets
        target.update(e["wallets"])

    illicit_scores = [anomaly_scores[w]["anomaly_score"] for w in illicit_wallets if w in anomaly_scores]
    legit_scores = [anomaly_scores[w]["anomaly_score"] for w in legit_wallets if w in anomaly_scores]

    sorted_wallets = sorted(anomaly_scores.items(), key=lambda kv: kv[1]["anomaly_score"], reverse=True)
    top_n = max(1, int(len(sorted_wallets) * top_pct))
    top_wallets = {w for w, _ in sorted_wallets[:top_n]}
    illicit_in_top = len(top_wallets & illicit_wallets)

    return {
        "illicit_wallets_scored": len(illicit_scores),
        "legit_wallets_scored": len(legit_scores),
        "mean_anomaly_score_illicit": round(mean(illicit_scores), 2) if illicit_scores else None,
        "mean_anomaly_score_legit": round(mean(legit_scores), 2) if legit_scores else None,
        "top_pct_examined": top_pct,
        "top_n_wallets": top_n,
        "illicit_wallets_in_top_pct": illicit_in_top,
        "illicit_recall_in_top_pct": round(illicit_in_top / len(illicit_wallets), 4) if illicit_wallets else None,
    }

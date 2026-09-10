"""
btc_anomaly.py — Trained anomaly detection for the TRACE-X Bitcoin pipeline.

Satisfies PS 26146 objective (iii): "Implement AI/ML detection use case ...
with a working model — not just rules" and the "Anomaly Detection" focus area
("flag statistically unusual transactions/flows").

This is additive: it does NOT replace peeling-chain/darknet-sweep detection
(those stay as strong rule-based signals — PS wants both). It adds a genuinely
trained Isolation Forest over wallet-level behavioral features, blended into
the final risk score, with SHAP-based per-wallet explainability.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import shap

FEATURE_COLS = [
    "total_in", "total_out", "net_flow",
    "num_in_txns", "num_out_txns",
    "avg_amount_in", "avg_amount_out", "std_amount",
    "time_span_hrs", "avg_inter_tx_hrs",
    "unique_counterparties", "fee_ratio", "script_type_diversity",
]


def extract_wallet_features(tx_df: pd.DataFrame) -> pd.DataFrame:
    """
    tx_df: long-format transaction rows — txid, wallet, role, amount,
    timestamp, fee, script_type (matches the existing dataset schema).
    Returns one row per wallet.
    """
    tx_df = tx_df.copy()
    tx_df["timestamp"] = pd.to_datetime(tx_df["timestamp"], format="ISO8601")

    rows = []
    for wallet, g in tx_df.groupby("wallet"):
        inflow = g[g.role == "output"]
        outflow = g[g.role == "input"]

        total_in = inflow.amount.sum()
        total_out = outflow.amount.sum()
        times = g.timestamp.sort_values()
        span_hrs = (times.max() - times.min()).total_seconds() / 3600 if len(times) > 1 else 0
        inter = times.diff().dropna().dt.total_seconds() / 3600
        avg_inter = inter.mean() if len(inter) else 0

        counterparties = set()
        for txid, tg in g.groupby("txid"):
            counterparties.update(tg.wallet.unique())
        counterparties.discard(wallet)

        rows.append({
            "wallet": wallet,
            "total_in": total_in,
            "total_out": total_out,
            "net_flow": total_in - total_out,
            "num_in_txns": len(inflow),
            "num_out_txns": len(outflow),
            "avg_amount_in": inflow.amount.mean() if len(inflow) else 0,
            "avg_amount_out": outflow.amount.mean() if len(outflow) else 0,
            "std_amount": g.amount.std() if len(g) > 1 else 0,
            "time_span_hrs": span_hrs,
            "avg_inter_tx_hrs": avg_inter,
            "unique_counterparties": len(counterparties),
            "fee_ratio": (g.fee.sum() / total_out) if total_out > 0 else 0,
            "script_type_diversity": g.script_type.nunique(),
        })

    feat_df = pd.DataFrame(rows).fillna(0).set_index("wallet")
    return feat_df


def train_isolation_forest(feat_df: pd.DataFrame, contamination: float = 0.08):
    """
    contamination ~ expected illicit fraction; 0.08 is a reasonable starting
    prior for this dataset's known CRITICAL+HIGH tier proportion — tune
    against your ground truth if you have it.
    """
    scaler = StandardScaler()
    X = scaler.fit_transform(feat_df[FEATURE_COLS])

    model = IsolationForest(
        n_estimators=300,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)
    return model, scaler


def score_wallets(model, scaler, feat_df: pd.DataFrame) -> pd.Series:
    """
    Returns anomaly_score in [0, 100], higher = more anomalous.
    """
    X = scaler.transform(feat_df[FEATURE_COLS])
    raw = model.score_samples(X)  # higher = more normal
    inverted = -raw
    normalized = (inverted - inverted.min()) / (inverted.max() - inverted.min() + 1e-9) * 100
    return pd.Series(normalized, index=feat_df.index, name="anomaly_score")


def explain_wallet(model, scaler, feat_df: pd.DataFrame, wallet: str, top_k: int = 5):
    """
    SHAP explanation for a single wallet's anomaly score.
    """
    X = scaler.transform(feat_df[FEATURE_COLS])
    row_idx = feat_df.index.get_loc(wallet)

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X[row_idx:row_idx + 1])
        contributions = shap_values[0]
    except Exception as e:
        explainer = shap.Explainer(model.score_samples, X, algorithm="permutation")
        sv = explainer(X[row_idx:row_idx + 1])
        contributions = sv.values[0]

    pairs = sorted(
        zip(FEATURE_COLS, contributions),
        key=lambda p: abs(p[1]),
        reverse=True,
    )[:top_k]

    return [
        {"feature": f, "impact": round(float(v), 4)}
        for f, v in pairs
    ]


def run_pipeline(tx_df: pd.DataFrame, contamination: float = 0.08):
    """
    Convenience entry point: extract features, train, score, return
    everything main.py needs to populate btc_cache.
    """
    feat_df = extract_wallet_features(tx_df)
    model, scaler = train_isolation_forest(feat_df, contamination=contamination)
    scores = score_wallets(model, scaler, feat_df)
    return {
        "features": feat_df,
        "model": model,
        "scaler": scaler,
        "anomaly_scores": scores,
    }

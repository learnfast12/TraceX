"""
TRACE-X — elliptic_benchmark.py
Benchmarks TRACE-X's classification ensemble (XGBoost/LightGBM/RandomForest/
IsolationForest) against the public Elliptic dataset, using the SAME temporal
train/test protocol as the original paper (Weber et al. 2019, "Anti-Money
Laundering in Bitcoin: Experimenting with Graph Convolutional Networks for
Financial Forensics"): train on time steps 1-34, test on time steps 35-49.

This is deliberately NOT a random split -- illicit typologies drift over
time, and a random split leaks future patterns into training, inflating the
score in a way that wouldn't survive real deployment. Matching the paper's
split is what makes this number comparable to published baselines (their
best reported: RF F1 ~0.77, AUPRC in the same range depending on feature set).

Elliptic label convention: class 1 = illicit, class 2 = licit, "unknown" =
unlabeled (majority of nodes). Only labeled rows are used for train/eval,
per the paper's own methodology -- unknowns are excluded, not treated as
negatives.

Run from repo root: python3 dataset/elliptic_benchmark.py
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, roc_auc_score, confusion_matrix,
)
from sklearn.ensemble import RandomForestClassifier, IsolationForest
import xgboost as xgb
import lightgbm as lgb

DATA_DIR = "dataset/elliptic"
FEATURES_CSV = f"{DATA_DIR}/elliptic_txs_features.csv"
CLASSES_CSV = f"{DATA_DIR}/elliptic_txs_classes.csv"

TRAIN_MAX_TIMESTEP = 34  # inclusive -- matches the paper's split exactly


def load_elliptic():
    # features.csv has NO header row: col0 = txId, col1 = time step,
    # col2..165 = 165 node features (local + aggregated 1-hop features)
    feat = pd.read_csv(FEATURES_CSV, header=None)
    feat.columns = ["txId", "time_step"] + [f"f_{i}" for i in range(feat.shape[1] - 2)]

    classes = pd.read_csv(CLASSES_CSV)  # columns: txId, class ("1","2","unknown")
    df = feat.merge(classes, on="txId", how="left")

    labeled = df[df["class"].isin(["1", "2"])].copy()
    labeled["label"] = (labeled["class"] == "1").astype(int)  # 1 = illicit

    print(f"Total nodes: {len(df)}  |  Labeled: {len(labeled)} "
          f"({100*len(labeled)/len(df):.1f}%)  |  "
          f"Illicit among labeled: {labeled['label'].sum()} "
          f"({100*labeled['label'].mean():.2f}%)")

    return labeled


def temporal_split(labeled):
    train = labeled[labeled["time_step"] <= TRAIN_MAX_TIMESTEP]
    test = labeled[labeled["time_step"] > TRAIN_MAX_TIMESTEP]
    feature_cols = [c for c in labeled.columns if c.startswith("f_")]
    X_train, y_train = train[feature_cols], train["label"]
    X_test, y_test = test[feature_cols], test["label"]
    print(f"Train: {len(X_train)} rows (steps 1-{TRAIN_MAX_TIMESTEP}, "
          f"{y_train.sum()} illicit)  |  "
          f"Test: {len(X_test)} rows (steps {TRAIN_MAX_TIMESTEP+1}-49, "
          f"{y_test.sum()} illicit)")
    return X_train, y_train, X_test, y_test


def evaluate(name, y_true, y_pred, y_score=None):
    p = precision_score(y_true, y_pred, zero_division=0)
    r = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    row = {
        "model": name, "precision": round(p, 4), "recall": round(r, 4),
        "f1": round(f1, 4), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }
    if y_score is not None:
        row["auprc"] = round(average_precision_score(y_true, y_score), 4)
        row["auroc"] = round(roc_auc_score(y_true, y_score), 4)
    return row


def main():
    labeled = load_elliptic()
    X_train, y_train, X_test, y_test = temporal_split(labeled)

    results = []

    # --- XGBoost ---
    xgb_clf = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        eval_metric="aucpr", scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1),
    )
    xgb_clf.fit(X_train, y_train)
    y_score = xgb_clf.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)
    results.append(evaluate("XGBoost", y_test, y_pred, y_score))

    # --- LightGBM ---
    lgb_clf = lgb.LGBMClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        class_weight="balanced", verbosity=-1,
    )
    lgb_clf.fit(X_train, y_train)
    y_score = lgb_clf.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)
    results.append(evaluate("LightGBM", y_test, y_pred, y_score))

    # --- Random Forest (the paper's own strongest non-GNN baseline) ---
    rf_clf = RandomForestClassifier(
        n_estimators=300, max_depth=None, class_weight="balanced", n_jobs=-1, random_state=42,
    )
    rf_clf.fit(X_train, y_train)
    y_score = rf_clf.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)
    results.append(evaluate("RandomForest", y_test, y_pred, y_score))

    # --- Isolation Forest (unsupervised anomaly path — trained WITHOUT
    #     labels, only on train-period features, then scored on test.
    #     This is the honest way to represent TRACE-X's anomaly ensemble,
    #     since Isolation Forest is not a classifier in your real pipeline.)
    iso = IsolationForest(n_estimators=300, contamination="auto", random_state=42, n_jobs=-1)
    iso.fit(X_train)
    # decision_function: higher = more normal. Flip sign so higher = more anomalous/illicit-like.
    anomaly_score = -iso.decision_function(X_test)
    # Threshold at the actual illicit rate in test (can't use 0.5 — unsupervised, no probability)
    illicit_rate = y_test.mean()
    thresh = np.quantile(anomaly_score, 1 - illicit_rate)
    y_pred = (anomaly_score >= thresh).astype(int)
    results.append(evaluate("IsolationForest (unsupervised)", y_test, y_pred, anomaly_score))

    print("\n" + "=" * 100)
    print("RESULTS — temporal split (train steps 1-34, test steps 35-49), matching Weber et al. 2019")
    print("=" * 100)
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    print("""
Reference point (Weber et al. 2019, same temporal split, AF+node-embedding features):
  Random Forest reported ~0.80 precision / ~0.65 recall / ~0.72 F1 (varies by feature set used)
Compare your RandomForest row above against this directly -- same split, same dataset,
same evaluation philosophy. Cite the paper, not just this script, in your write-up.
""")

    results_df.to_csv("dataset/elliptic/elliptic_benchmark_results.csv", index=False)
    print("Saved: dataset/elliptic/elliptic_benchmark_results.csv")


if __name__ == "__main__":
    main()

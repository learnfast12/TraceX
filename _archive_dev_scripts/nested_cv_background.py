import sys, time, json
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, precision_score, recall_score, f1_score
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

CSV_PATH = '/home/x0_shravan_0x/Downloads/DataSet.csv'
TARGET = 'F3924'
OUT_PATH = '/home/x0_shravan_0x/Tracenetx/backend/nested_cv_results.json'

with open('/home/x0_shravan_0x/Tracenetx/backend/top_100_features_clean.txt') as f:
    top_features = [line.strip() for line in f if line.strip()]

df = pd.read_csv(CSV_PATH)
df = df.rename(columns={df.columns[0]: 'account_id'})
X = df[top_features].copy()
for col in X.columns:
    if not pd.api.types.is_numeric_dtype(X[col]):
        X[col] = pd.factorize(X[col].astype(str))[0]
X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
y = df[TARGET]

N_REPEATS = 5
N_OUTER = 5
N_INNER = 3

precisions, recalls, f1s, aucs, thresholds_used = [], [], [], [], []
total = N_REPEATS * N_OUTER
done = 0
t0 = time.time()

def make_model():
    base = xgb.XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.08,
                              scale_pos_weight=10, random_state=42,
                              eval_metric='logloss', verbosity=0)
    return CalibratedClassifierCV(base, method='sigmoid', cv=2)

for repeat in range(N_REPEATS):
    outer_skf = StratifiedKFold(n_splits=N_OUTER, shuffle=True, random_state=repeat)
    for outer_train_idx, outer_test_idx in outer_skf.split(X, y):
        X_outer_train, X_outer_test = X.iloc[outer_train_idx], X.iloc[outer_test_idx]
        y_outer_train, y_outer_test = y.iloc[outer_train_idx], y.iloc[outer_test_idx]

        inner_skf = StratifiedKFold(n_splits=N_INNER, shuffle=True, random_state=repeat)
        inner_oof_proba = np.zeros(len(X_outer_train))

        for inner_train_idx, inner_val_idx in inner_skf.split(X_outer_train, y_outer_train):
            X_it, X_iv = X_outer_train.iloc[inner_train_idx], X_outer_train.iloc[inner_val_idx]
            y_it = y_outer_train.iloc[inner_train_idx]

            scaler = MinMaxScaler()
            X_it_s = scaler.fit_transform(X_it)
            X_iv_s = scaler.transform(X_iv)

            try:
                sm = SMOTE(random_state=42, k_neighbors=min(5, y_it.sum() - 1))
                X_it_r, y_it_r = sm.fit_resample(X_it_s, y_it)
            except Exception:
                X_it_r, y_it_r = X_it_s, y_it

            m = make_model()
            m.fit(X_it_r, y_it_r)
            inner_oof_proba[inner_val_idx] = m.predict_proba(X_iv_s)[:, 1]

        prec_a, rec_a, th_a = precision_recall_curve(y_outer_train, inner_oof_proba)
        th_a_full = list(th_a) + [1.0]
        f1_a = [2 * p * r / (p + r) if (p + r) > 0 else 0 for p, r in zip(prec_a, rec_a)]
        best_threshold = th_a_full[int(np.argmax(f1_a))]

        scaler = MinMaxScaler()
        X_ot_s = scaler.fit_transform(X_outer_train)
        X_ote_s = scaler.transform(X_outer_test)
        try:
            sm = SMOTE(random_state=42, k_neighbors=min(5, y_outer_train.sum() - 1))
            X_ot_r, y_ot_r = sm.fit_resample(X_ot_s, y_outer_train)
        except Exception:
            X_ot_r, y_ot_r = X_ot_s, y_outer_train

        mf = make_model()
        mf.fit(X_ot_r, y_ot_r)
        test_p = mf.predict_proba(X_ote_s)[:, 1]
        test_pred = (test_p >= best_threshold).astype(int)

        if y_outer_test.sum() > 0:
            precisions.append(precision_score(y_outer_test, test_pred, zero_division=0))
            recalls.append(recall_score(y_outer_test, test_pred, zero_division=0))
            f1s.append(f1_score(y_outer_test, test_pred, zero_division=0))
            aucs.append(roc_auc_score(y_outer_test, test_p))
            thresholds_used.append(best_threshold)

        done += 1
        elapsed = time.time() - t0
        eta = (elapsed / done) * (total - done)
        print(f"[{done}/{total}] fold done ({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)", flush=True)

results = {
    "method": f"Stratified nested CV, {N_REPEATS} repeats x {N_OUTER} outer x {N_INNER} inner folds, sigmoid-calibrated XGBoost, F1-optimal threshold selected on inner OOF predictions only",
    "precision_mean": round(float(np.mean(precisions)), 4),
    "precision_std": round(float(np.std(precisions)), 4),
    "recall_mean": round(float(np.mean(recalls)), 4),
    "recall_std": round(float(np.std(recalls)), 4),
    "f1_mean": round(float(np.mean(f1s)), 4),
    "f1_std": round(float(np.std(f1s)), 4),
    "auc_roc_mean": round(float(np.mean(aucs)), 4),
    "auc_roc_std": round(float(np.std(aucs)), 4),
    "n_outer_evaluations": len(precisions),
    "threshold_min": round(float(min(thresholds_used)), 4),
    "threshold_max": round(float(max(thresholds_used)), 4),
    "threshold_mean": round(float(np.mean(thresholds_used)), 4),
    "runtime_seconds": round(time.time() - t0, 1)
}

with open(OUT_PATH, 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 60)
print("FINAL RESULTS")
print("=" * 60)
for k, v in results.items():
    print(f"  {k}: {v}")
print(f"\nSaved to {OUT_PATH}")

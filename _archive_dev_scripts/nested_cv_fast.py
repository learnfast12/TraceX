import sys, time
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, precision_score, recall_score, f1_score
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

CSV_PATH = '/home/x0_shravan_0x/Downloads/DataSet.csv'
TARGET = 'F3924'

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

N_REPEATS = 2
N_OUTER = 5
N_INNER = 2

precisions, recalls, f1s, aucs = [], [], [], []
total = N_REPEATS * N_OUTER
done = 0
t0 = time.time()

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
            m = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1,
                                   scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
            m.fit(X_it_r, y_it_r)
            inner_oof_proba[inner_val_idx] = m.predict_proba(X_iv_s)[:, 1]

        prec_a, rec_a, th_a = precision_recall_curve(y_outer_train, inner_oof_proba)
        valid = [(p, r, t) for p, r, t in zip(prec_a, rec_a, list(th_a) + [1.0]) if r >= 0.85]
        best_t = max(valid, key=lambda x: x[0])[2] if valid else 0.5

        scaler = MinMaxScaler()
        X_ot_s = scaler.fit_transform(X_outer_train)
        X_ote_s = scaler.transform(X_outer_test)
        try:
            sm = SMOTE(random_state=42, k_neighbors=min(5, y_outer_train.sum() - 1))
            X_ot_r, y_ot_r = sm.fit_resample(X_ot_s, y_outer_train)
        except Exception:
            X_ot_r, y_ot_r = X_ot_s, y_outer_train
        mf = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1,
                                scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
        mf.fit(X_ot_r, y_ot_r)
        test_p = mf.predict_proba(X_ote_s)[:, 1]
        test_pred = (test_p >= best_t).astype(int)

        if y_outer_test.sum() > 0:
            precisions.append(precision_score(y_outer_test, test_pred, zero_division=0))
            recalls.append(recall_score(y_outer_test, test_pred, zero_division=0))
            f1s.append(f1_score(y_outer_test, test_pred, zero_division=0))
            aucs.append(roc_auc_score(y_outer_test, test_p))

        done += 1
        print(f"[{done}/{total}] outer fold done ({time.time()-t0:.0f}s elapsed)")

print(f"\nPrecision: {np.mean(precisions):.4f} +/- {np.std(precisions):.4f}")
print(f"Recall:    {np.mean(recalls):.4f} +/- {np.std(recalls):.4f}")
print(f"F1:        {np.mean(f1s):.4f} +/- {np.std(f1s):.4f}")
print(f"AUC-ROC:   {np.mean(aucs):.4f} +/- {np.std(aucs):.4f}")

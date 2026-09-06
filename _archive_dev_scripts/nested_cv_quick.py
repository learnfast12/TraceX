import sys, time
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

N_OUTER = 5
precisions, recalls, f1s, aucs, thresholds_used = [], [], [], [], []
t0 = time.time()

def make_model():
    base = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1,
                              scale_pos_weight=10, random_state=42,
                              eval_metric='logloss', verbosity=0)
    return CalibratedClassifierCV(base, method='sigmoid', cv=2)

outer_skf = StratifiedKFold(n_splits=N_OUTER, shuffle=True, random_state=42)
for i, (outer_train_idx, outer_test_idx) in enumerate(outer_skf.split(X, y)):
    X_outer_train, X_outer_test = X.iloc[outer_train_idx], X.iloc[outer_test_idx]
    y_outer_train, y_outer_test = y.iloc[outer_train_idx], y.iloc[outer_test_idx]

    # single inner split for threshold (not full inner CV) to keep this fast
    from sklearn.model_selection import train_test_split
    X_it, X_iv, y_it, y_iv = train_test_split(X_outer_train, y_outer_train, test_size=0.25,
                                               random_state=42, stratify=y_outer_train)
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
    iv_proba = m.predict_proba(X_iv_s)[:, 1]

    prec_a, rec_a, th_a = precision_recall_curve(y_iv, iv_proba)
    th_a_full = list(th_a) + [1.0]
    f1_a = [2*p*r/(p+r) if (p+r) > 0 else 0 for p, r in zip(prec_a, rec_a)]
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

    precisions.append(precision_score(y_outer_test, test_pred, zero_division=0))
    recalls.append(recall_score(y_outer_test, test_pred, zero_division=0))
    f1s.append(f1_score(y_outer_test, test_pred, zero_division=0))
    aucs.append(roc_auc_score(y_outer_test, test_p))
    thresholds_used.append(best_threshold)
    print(f"[{i+1}/{N_OUTER}] done ({time.time()-t0:.0f}s)")

print(f"\nPrecision: {np.mean(precisions):.4f} +/- {np.std(precisions):.4f}")
print(f"Recall:    {np.mean(recalls):.4f} +/- {np.std(recalls):.4f}")
print(f"F1:        {np.mean(f1s):.4f} +/- {np.std(f1s):.4f}")
print(f"AUC-ROC:   {np.mean(aucs):.4f} +/- {np.std(aucs):.4f}")

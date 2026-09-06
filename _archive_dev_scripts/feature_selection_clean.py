import sys
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

CSV_PATH = '/home/x0_shravan_0x/Downloads/DataSet.csv'
DICT_PATH = '/home/x0_shravan_0x/Downloads/Description_1_.xlsx'
TARGET = 'F3924'
TOP_N = 100

# Known leakage / non-behavioral fields to hard-exclude
EXCLUDE = {
    'F2230',  # MNTH - month of data collection, not a behavioral feature
    'F3898', 'F3899',  # MIN/MAX_RESOLVE_DAYS - only exists after investigation closed
    'F3900', 'F3901', 'F3902', 'F3903', 'F3904', 'F3905', 'F3906', 'F3907',
    'F3908', 'F3909', 'F3910', 'F3911',  # alert description flags - alert already fired
    'F3912', 'F3913', 'F3914', 'F3915',  # resolution status flags - investigation outcome
    'F3916', 'F3917', 'F3918',  # L1/L2/L3_FLG - pre-existing risk tier from bank's own system
    'F3919', 'F3920', 'F3921', 'F3922', 'F3923',  # alert counts - already-flagged history
    'F3895', 'F3896', 'F3897',  # MIN/MAX_INC_SCORE + CNT_INC_SCR_GT650 - internal incident/risk score, not raw behavior
}

print("=" * 60)
print("STEP 0: Scanning data dictionary for other suspicious 'status/resolution/flag' fields")
print("=" * 60)
dd = pd.read_excel(DICT_PATH, sheet_name='Data_Dicitionary')
suspicious_keywords = ['fraud', 'suspect', 'resolution', 'status', 'flag', 'alert', 'stp', 'decision', 'action_taken']
suspicious = dd[dd['Description'].astype(str).str.lower().str.contains('|'.join(suspicious_keywords), na=False)]
print(f"Found {len(suspicious)} potentially suspicious fields (review before trusting):")
print(suspicious[['Feature', 'Variable Name', 'Description']].to_string(index=False))
print(f"\nCurrently hard-excluded: {EXCLUDE}")
print("If any others above look like post-hoc labels, add them to EXCLUDE and rerun.")

print("\n" + "=" * 60)
print("STEP 1: Loading dataset, dropping excluded leakage columns")
print("=" * 60)
df = pd.read_csv(CSV_PATH)
id_col = df.columns[0]
df = df.rename(columns={id_col: 'account_id'})

feature_cols = [c for c in df.columns if c.startswith('F') and c != TARGET and c not in EXCLUDE]
print(f"Total candidate features (after exclusion): {len(feature_cols)}")
print(f"Total accounts: {len(df)}, mules: {int(df[TARGET].sum())} ({df[TARGET].mean()*100:.2f}%)")

X = df[feature_cols].copy()
for col in X.columns:
    if not pd.api.types.is_numeric_dtype(X[col]):
        le = LabelEncoder()
        X[col] = X[col].astype(str).fillna('MISSING')
        X[col] = le.fit_transform(X[col])
X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
y = df[TARGET]

print("\n" + "=" * 60)
print("STEP 2: Baseline XGBoost on cleaned features -> importance ranking")
print("=" * 60)
X_train_full, X_test_full, y_train_full, y_test_full = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
baseline = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0
)
baseline.fit(X_train_full, y_train_full)

importances = pd.Series(baseline.feature_importances_, index=feature_cols).sort_values(ascending=False)
top_features = importances.head(TOP_N).index.tolist()

print(f"\nTop 20 features by importance (should now look diverse, no single dominant feature):")
for feat, imp in importances.head(20).items():
    print(f"  {feat:10s}  importance={imp:.5f}")

print("\n" + "=" * 60)
print(f"STEP 3: Elite ensemble on top {TOP_N} clean features")
print("=" * 60)
X_sel = X[top_features]
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_sel)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)
smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

xgb_model = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
xgb_model.fit(X_train_res, y_train_res)
lgb_model = lgb.LGBMClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
    class_weight='balanced', random_state=42, verbose=-1)
lgb_model.fit(X_train_res, y_train_res)
rf_model = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
rf_model.fit(X_train_res, y_train_res)

xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
lgb_proba = lgb_model.predict_proba(X_test)[:, 1]
rf_proba = rf_model.predict_proba(X_test)[:, 1]
ensemble_proba = 0.5 * xgb_proba + 0.3 * lgb_proba + 0.2 * rf_proba
ensemble_pred = (ensemble_proba >= 0.5).astype(int)

print("\n--- HOLDOUT TEST SET PERFORMANCE (should now look realistic, not perfect) ---")
print(classification_report(y_test, ensemble_pred))
print(f"AUC-ROC (ensemble): {roc_auc_score(y_test, ensemble_proba):.4f}")

print("\n" + "=" * 60)
print(f"STEP 4: 5-fold cross-validation on clean top {TOP_N} features")
print("=" * 60)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_model = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
cv_scores = cross_val_score(cv_model, X_scaled, y, cv=skf, scoring='roc_auc')
print(f"Per fold: {[round(s,4) for s in cv_scores]}")
print(f"Mean AUC-ROC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

with open('/home/x0_shravan_0x/Tracenetx/backend/top_100_features_clean.txt', 'w') as f:
    for feat in top_features:
        f.write(feat + '\n')
print("\nSaved clean feature list to backend/top_100_features_clean.txt")
print("DONE.")

import sys
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

CSV_PATH = '/home/x0_shravan_0x/Downloads/DataSet.csv'
TARGET = 'F3924'
TOP_N = 100

print("=" * 60)
print("STEP 1: Loading full dataset (all 3,924 features)")
print("=" * 60)
df = pd.read_csv(CSV_PATH)
id_col = df.columns[0]
df = df.rename(columns={id_col: 'account_id'})

feature_cols = [c for c in df.columns if c.startswith('F') and c != TARGET]
print(f"Total candidate features: {len(feature_cols)}")
print(f"Total accounts: {len(df)}, mules: {int(df[TARGET].sum())} ({df[TARGET].mean()*100:.2f}%)")

print("\n" + "=" * 60)
print("STEP 2: Auto-encoding non-numeric columns (robust check)")
print("=" * 60)
X = df[feature_cols].copy()
encoded_count = 0
encoded_cols = []
for col in X.columns:
    if not pd.api.types.is_numeric_dtype(X[col]):
        le = LabelEncoder()
        X[col] = X[col].astype(str).fillna('MISSING')
        X[col] = le.fit_transform(X[col])
        encoded_count += 1
        encoded_cols.append(col)

# force everything to numeric, catch any stragglers
X = X.apply(pd.to_numeric, errors='coerce')
print(f"Label-encoded {encoded_count} categorical columns")
print(f"Encoded columns: {encoded_cols}")

X = X.fillna(0)
y = df[TARGET]

print("\n" + "=" * 60)
print("STEP 3: Baseline XGBoost on ALL features -> importance ranking")
print("=" * 60)
X_train_full, X_test_full, y_train_full, y_test_full = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

baseline = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0
)
baseline.fit(X_train_full, y_train_full)

importances = pd.Series(baseline.feature_importances_, index=feature_cols)
importances = importances.sort_values(ascending=False)
top_features = importances.head(TOP_N).index.tolist()

print(f"\nTop 20 features by importance:")
for feat, imp in importances.head(20).items():
    print(f"  {feat:10s}  importance={imp:.5f}")

print(f"\nSelected top {TOP_N} features for elite model")

print("\n" + "=" * 60)
print(f"STEP 4: Elite ensemble on top {TOP_N} features (proper train/test split, SMOTE on train only)")
print("=" * 60)
X_sel = X[top_features]
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_sel)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)

smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

xgb_model = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0
)
xgb_model.fit(X_train_res, y_train_res)

lgb_model = lgb.LGBMClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    class_weight='balanced', random_state=42, verbose=-1
)
lgb_model.fit(X_train_res, y_train_res)

rf_model = RandomForestClassifier(
    n_estimators=200, class_weight='balanced', random_state=42
)
rf_model.fit(X_train_res, y_train_res)

xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
lgb_proba = lgb_model.predict_proba(X_test)[:, 1]
rf_proba = rf_model.predict_proba(X_test)[:, 1]
ensemble_proba = 0.5 * xgb_proba + 0.3 * lgb_proba + 0.2 * rf_proba
ensemble_pred = (ensemble_proba >= 0.5).astype(int)

print("\n--- HOLDOUT TEST SET PERFORMANCE ---")
print(classification_report(y_test, ensemble_pred))
print(f"AUC-ROC (ensemble): {roc_auc_score(y_test, ensemble_proba):.4f}")

print("\n" + "=" * 60)
print(f"STEP 5: 5-fold cross-validation on top {TOP_N} features (XGBoost, realistic estimate)")
print("=" * 60)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_model = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0
)
cv_scores = cross_val_score(cv_model, X_scaled, y, cv=skf, scoring='roc_auc')
print(f"Per fold: {[round(s,4) for s in cv_scores]}")
print(f"Mean AUC-ROC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

print("\n" + "=" * 60)
print("STEP 6: Saving selected feature list for pipeline integration")
print("=" * 60)
with open('/home/x0_shravan_0x/Tracenetx/backend/top_100_features.txt', 'w') as f:
    for feat in top_features:
        f.write(feat + '\n')
print("Saved to backend/top_100_features.txt")
print("\nDONE.")

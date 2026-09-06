import sys
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import xgboost as xgb

df = pd.read_csv('/home/x0_shravan_0x/Downloads/DataSet.csv')
target_col = "F3924"

# Correctly-scoped leak exclusion: only the two columns actually shown to leak
correctly_excluded = {"F2230", "F3912"}

# All feature columns except id, target, and the two real leaks
id_col = df.columns[0]
all_features = [c for c in df.columns if c not in (id_col, target_col) and c not in correctly_excluded]

# Keep only numeric-coercible columns for this quick comparison (skip categorical encoding complexity for now)
numeric_features = []
for c in all_features:
    if pd.api.types.is_numeric_dtype(df[c]):
        numeric_features.append(c)

print(f"Total candidate features after correct leak removal: {len(numeric_features)}")

X = df[numeric_features].fillna(0)
y = df[target_col]

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
aucs = []
for fold, (train_idx, test_idx) in enumerate(skf.split(X, y)):
    X_train_raw, X_test_raw = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    smote = SMOTE(random_state=42, k_neighbors=min(5, int(y_train.sum()) - 1))
    X_train, y_train = smote.fit_resample(X_train, y_train)

    model = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1,
                               scale_pos_weight=10, random_state=42,
                               eval_metric='logloss', verbosity=0)
    model.fit(X_train, y_train)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    aucs.append(auc)
    print(f"Fold {fold}: AUC-ROC = {auc:.4f}")

print(f"\nMean AUC-ROC (correctly-scoped leak removal, ALL {len(numeric_features)} numeric features): {np.mean(aucs):.4f} (+/- {np.std(aucs):.4f})")
print(f"For comparison, our earlier over-broad-exclusion result (100 SHAP-selected features): 0.9923 (+/-0.0099)")

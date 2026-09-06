import sys
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
from ml_pipeline import TraceNetXMLPipeline
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import xgboost as xgb
import numpy as np

pipe = TraceNetXMLPipeline()
df = pipe.load_real_dataset('/home/x0_shravan_0x/Downloads/DataSet.csv')

feature_cols = pipe.FINALIZED_FEATURES
X = df[feature_cols].fillna(0)
y = df[pipe.TARGET_COL]

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
aucs = []

for fold, (train_idx, test_idx) in enumerate(skf.split(X, y)):
    X_train_raw, X_test_raw = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    # Scaler fit on TRAIN ONLY (fixes the leak in the original code)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
    X_train, y_train = smote.fit_resample(X_train, y_train)

    model = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1,
                               scale_pos_weight=10, random_state=42,
                               eval_metric='logloss', verbosity=0)
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    aucs.append(auc)
    print(f"Fold {fold}: AUC-ROC = {auc:.4f}  (test pos={int(y_test.sum())})")

print(f"\nMean AUC-ROC: {np.mean(aucs):.4f} (+/- {np.std(aucs):.4f})")

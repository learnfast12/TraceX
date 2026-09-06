import sys
sys.path.insert(0, '/home/x0_shravan_0x/Tracenetx/backend')
import numpy as np
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import precision_recall_curve, roc_auc_score, classification_report
from ml_pipeline import TraceNetXMLPipeline

pipe = TraceNetXMLPipeline()
df = pipe.load_real_dataset('/home/x0_shravan_0x/Downloads/DataSet.csv')

feature_cols = pipe.FINALIZED_FEATURES
X = df[feature_cols].fillna(0)
y = df[pipe.TARGET_COL]
X_scaled = pipe.scaler.fit_transform(X)

# 5-fold stratified CV — realistic performance estimate
print("=== 5-FOLD CROSS-VALIDATION (AUC-ROC) ===")
model = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1,
                           scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(model, X_scaled, y, cv=skf, scoring='roc_auc')
print(f"AUC-ROC per fold: {scores}")
print(f"Mean AUC-ROC: {scores.mean():.4f} (+/- {scores.std():.4f})")

# Threshold tuning on one split
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
model.fit(X_train, y_train)
y_proba = model.predict_proba(X_test)[:, 1]

precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)
print("\n=== THRESHOLD SWEEP (target: recall>85%, precision>70%) ===")
for p, r, t in zip(precisions, recalls, list(thresholds) + [1.0]):
    if r >= 0.85:
        print(f"threshold={t:.3f}  precision={p:.3f}  recall={r:.3f}")

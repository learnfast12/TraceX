import re
path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

if "REAL BOI DATASET TRAINING PATH" in content:
    print("Already patched, skipping.")
else:
    new_methods = '''
    FINALIZED_FEATURES = [
        "F115", "F321", "F527", "F531", "F670", "F1692", "F2082", "F2122",
        "F2582", "F2678", "F2737", "F2956", "F3043", "F3836", "F3887",
        "F3889", "F3891", "F3894"
    ]
    TARGET_COL = "F3924"

    def load_real_dataset(self, csv_path):
        print(f"[TraceNetX ML] Loading real dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        id_col = df.columns[0]
        df = df.rename(columns={id_col: "account_id"})
        keep_cols = ["account_id"] + self.FINALIZED_FEATURES + [self.TARGET_COL]
        df = df[keep_cols]
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        return df

    def train_on_real_data(self, df):
        feature_cols = self.FINALIZED_FEATURES
        self.feature_names = feature_cols
        X = df[feature_cols].fillna(0)
        y = df[self.TARGET_COL]
        X_scaled = self.scaler.fit_transform(X)
        print("[TraceNetX ML] Applying SMOTE...")
        try:
            smote = SMOTE(random_state=42)
            X_res, y_res = smote.fit_resample(X_scaled, y)
        except Exception as e:
            print(f"[TraceNetX ML] SMOTE failed ({e}), using raw data")
            X_res, y_res = X_scaled, y
        X_train, X_test, y_train, y_test = train_test_split(X_res, y_res, test_size=0.2, random_state=42, stratify=y_res)
        print("[TraceNetX ML] Training XGBoost...")
        self.xgb_model = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, scale_pos_weight=10, random_state=42, eval_metric='logloss', verbosity=0)
        self.xgb_model.fit(X_train, y_train)
        print("[TraceNetX ML] Training LightGBM...")
        self.lgb_model = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, class_weight='balanced', random_state=42, verbose=-1)
        self.lgb_model.fit(X_train, y_train)
        print("[TraceNetX ML] Training Random Forest...")
        self.rf_model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
        self.rf_model.fit(X_train, y_train)
        print("[TraceNetX ML] Training Isolation Forest...")
        self.iso_forest = IsolationForest(contamination=0.01, random_state=42)
        self.iso_forest.fit(X_scaled)
        print("[TraceNetX ML] Building SHAP explainer...")
        self.explainer = shap.TreeExplainer(self.xgb_model)
        self.is_trained = True
        y_pred = self.xgb_model.predict(X_test)
        y_proba = self.xgb_model.predict_proba(X_test)[:, 1]
        print("\\n[TraceNetX ML] === REAL DATA MODEL PERFORMANCE ===")
        print(classification_report(y_test, y_pred))
        print(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.4f}")
        return X_test, y_test

    def predict_on_real_data(self, df):
        if not self.is_trained:
            raise RuntimeError("Call train_on_real_data() first.")
        feature_cols = self.FINALIZED_FEATURES
        X = df[feature_cols].fillna(0)
        X_scaled = self.scaler.transform(X)
        xgb_proba = self.xgb_model.predict_proba(X_scaled)[:, 1]
        lgb_proba = self.lgb_model.predict_proba(X_scaled)[:, 1]
        rf_proba = self.rf_model.predict_proba(X_scaled)[:, 1]
        ensemble_proba = (0.5 * xgb_proba + 0.3 * lgb_proba + 0.2 * rf_proba)
        iso_scores = self.iso_forest.decision_function(X_scaled)
        iso_normalized = 1 - (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min() + 1e-9)
        final_scores = (0.7 * ensemble_proba + 0.3 * iso_normalized) * 100
        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            score = float(final_scores[i])
            level, action, _ = self.classify_risk(score, {})
            shap_explanation = self.get_shap_explanation(X_scaled[i:i+1])
            results.append({'account_id': row['account_id'], 'risk_score': round(score, 2), 'risk_level': level, 'recommended_action': action, 'actual_label': int(row[self.TARGET_COL]), 'shap_explanation': shap_explanation})
        return sorted(results, key=lambda x: x['risk_score'], reverse=True)
'''
    marker = "# Global instance"
    content = content.replace(marker, new_methods.strip("\n") + "\n\n" + marker)
    with open(path_backend, "w") as f:
        f.write(content)
    print("Patched successfully.")

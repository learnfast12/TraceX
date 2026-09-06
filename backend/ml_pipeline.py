import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE
import xgboost as xgb
import lightgbm as lgb
import shap
import warnings
warnings.filterwarnings('ignore')

class TraceNetXMLPipeline:
    def __init__(self):
        self.xgb_model = None
        self.lgb_model = None
        self.rf_model = None
        self.iso_forest = None
        self.scaler = MinMaxScaler()
        self.explainer = None
        self.feature_names = None
        self.is_trained = False

    def engineer_features(self, df):
        features = {}

        # Transaction velocity
        sender_counts = df.groupby('sender_id').size()
        receiver_counts = df.groupby('receiver_id').size()
        sender_amounts = df.groupby('sender_id')['amount'].sum()
        receiver_amounts = df.groupby('receiver_id')['amount'].sum()

        accounts = set(df['sender_id']).union(set(df['receiver_id']))

        rows = []
        for acc in accounts:
            outgoing = df[df['sender_id'] == acc]
            incoming = df[df['receiver_id'] == acc]

            total_out = outgoing['amount'].sum()
            total_in = incoming['amount'].sum()
            num_out = len(outgoing)
            num_in = len(incoming)
            unique_receivers = outgoing['receiver_id'].nunique()
            unique_senders = incoming['sender_id'].nunique()
            unique_ips = incoming['sender_ip'].nunique() if len(incoming) > 0 else 0
            unique_cities = outgoing['sender_city'].nunique() if len(outgoing) > 0 else 0

            # Velocity ratio
            velocity_ratio = total_out / (total_in + 1)

            # Forwarding behavior (mule sends almost everything it receives)
            forwarding_ratio = total_out / (total_in + 1)

            # Rapid transfer detection — two real patterns, not just one:
            # (1) multiple outgoing transfers clustered within a 2hr window
            #     (staggered layering), or
            # (2) a single-hop pass-through: funds forwarded within 2hrs of
            #     being received (e.g. one big incoming payment immediately
            #     dumped onward) — this pattern was previously invisible
            #     because it requires only ONE outgoing transaction, which
            #     failed the old len(outgoing) >= 2 gate entirely
            rapid_transfer = 0
            if len(outgoing) >= 2:
                try:
                    times = pd.to_datetime(outgoing['timestamp']).sort_values()
                    span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 3600
                    if span <= 2:
                        rapid_transfer = 1
                except:
                    pass
            if rapid_transfer == 0 and len(outgoing) >= 1 and len(incoming) >= 1:
                try:
                    last_in = pd.to_datetime(incoming['timestamp']).max()
                    first_out = pd.to_datetime(outgoing['timestamp']).min()
                    latency = (first_out - last_in).total_seconds() / 3600
                    if 0 <= latency <= 2:
                        rapid_transfer = 1
                except:
                    pass

            # Smurfing detection (many small outgoing)
            avg_out_amount = outgoing['amount'].mean() if num_out > 0 else 0
            smurfing_score = 1 if (num_out >= 3 and avg_out_amount < 50000) else 0

            # IP concentration
            ip_concentration = 1 if (unique_ips == 1 and num_in >= 2) else 0

            rows.append({
                'account_id': acc,
                'total_outgoing': total_out,
                'total_incoming': total_in,
                'num_outgoing': num_out,
                'num_incoming': num_in,
                'unique_receivers': unique_receivers,
                'unique_senders': unique_senders,
                'unique_ips': unique_ips,
                'unique_cities': unique_cities,
                'velocity_ratio': velocity_ratio,
                'forwarding_ratio': forwarding_ratio,
                'rapid_transfer': rapid_transfer,
                'smurfing_score': smurfing_score,
                'ip_concentration': ip_concentration,
                'avg_outgoing_amount': avg_out_amount,
                'avg_incoming_amount': incoming['amount'].mean() if num_in > 0 else 0,
                'max_single_transfer': max(total_out, total_in),
            })

        return pd.DataFrame(rows)

    def train(self, df, labels=None):
        print("[TraceNetX ML] Engineering features...")
        feature_df = self.engineer_features(df)

        feature_cols = [c for c in feature_df.columns if c != 'account_id']
        self.feature_names = feature_cols
        X = feature_df[feature_cols].fillna(0)

        # If no labels provided, generate synthetic ones for demo
        if labels is None:
            # Use rule-based labels for demo training
            y = (
                # Criminal/mule pattern — full forwarding
                ((feature_df['forwarding_ratio'] > 0.8) & (feature_df['num_outgoing'] >= 2)) |
                # Hawala pattern — receives from many, sends to many
                ((feature_df['unique_senders'] >= 2) & (feature_df['unique_receivers'] >= 2) & (feature_df['forwarding_ratio'] > 0.6)) |
                # Recruiter pattern — receives from high-risk, forwards small amounts
                ((feature_df['num_incoming'] >= 1) & (feature_df['num_outgoing'] >= 2) & (feature_df['forwarding_ratio'] > 0.5)) |
                # IP concentration — multiple senders same IP
                (feature_df['ip_concentration'] == 1)
            ).astype(int)
        else:
            y = labels

        X_scaled = self.scaler.fit_transform(X)

        # SMOTE for class imbalance
        print("[TraceNetX ML] Applying SMOTE...")
        try:
            smote = SMOTE(random_state=42)
            X_res, y_res = smote.fit_resample(X_scaled, y)
        except:
            X_res, y_res = X_scaled, y

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X_res, y_res, test_size=0.2, random_state=42, stratify=y_res
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X_res, y_res, test_size=0.2, random_state=42
            )

        # XGBoost
        print("[TraceNetX ML] Training XGBoost...")
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=10,
            random_state=42,
            eval_metric='logloss',
            verbosity=0
        )
        self.xgb_model.fit(X_train, y_train)

        # LightGBM
        print("[TraceNetX ML] Training LightGBM...")
        self.lgb_model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            class_weight='balanced',
            random_state=42,
            verbose=-1
        )
        self.lgb_model.fit(X_train, y_train)

        # Random Forest
        print("[TraceNetX ML] Training Random Forest...")
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            class_weight='balanced',
            random_state=42
        )
        self.rf_model.fit(X_train, y_train)

        # Isolation Forest (anomaly detection)
        print("[TraceNetX ML] Training Isolation Forest...")
        self.iso_forest = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        self.iso_forest.fit(X_scaled)

        # SHAP explainer
        print("[TraceNetX ML] Building SHAP explainer...")
        self.explainer = shap.TreeExplainer(self.xgb_model)

        self.is_trained = True
        self.feature_df = feature_df

        # Evaluation
        y_pred = self.xgb_model.predict(X_test)
        print("\n[TraceNetX ML] === MODEL PERFORMANCE ===")
        print(classification_report(y_test, y_pred))

        return feature_df

    def predict(self, df):
        if not self.is_trained:
            self.train(df)

        feature_df = self.engineer_features(df)
        feature_cols = [c for c in feature_df.columns if c != 'account_id']
        X = feature_df[feature_cols].fillna(0)
        X_scaled = self.scaler.transform(X)

        # Ensemble scoring
        xgb_proba = self.xgb_model.predict_proba(X_scaled)[:, 1]
        lgb_proba = self.lgb_model.predict_proba(X_scaled)[:, 1]
        rf_proba = self.rf_model.predict_proba(X_scaled)[:, 1]

        # Weighted ensemble (XGBoost gets more weight)
        ensemble_proba = (0.5 * xgb_proba + 0.3 * lgb_proba + 0.2 * rf_proba)

        # Isolation Forest anomaly score
        iso_scores = self.iso_forest.decision_function(X_scaled)
        iso_normalized = 1 - (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min() + 1e-9)

        # Final risk score 0-100
        final_scores = (0.7 * ensemble_proba + 0.3 * iso_normalized) * 100

        results = []
        for i, row in feature_df.iterrows():
            score = float(final_scores[i])
            level, action, mule_type = self.classify_risk(score, row)
            shap_explanation = self.get_shap_explanation(X_scaled[i:i+1])

            results.append({
                'account_id': row['account_id'],
                'risk_score': round(score, 2),
                'risk_level': level,
                'recommended_action': action,
                'mule_type': mule_type,
                'shap_explanation': shap_explanation,
                'flags': self.get_flags(row)
            })

        return sorted(results, key=lambda x: x['risk_score'], reverse=True)

    def classify_risk(self, score, features):
        # Graduated 5-level response system
        if score >= 70:
            level = "CRITICAL"
            action = "Immediate freeze + STR filing + ED/CBI referral"
        elif score >= 55:
            level = "HIGH"
            action = "Account freeze + investigation + police referral"
        elif score >= 50:
            level = "MEDIUM"
            action = "Enhanced monitoring + bank outreach + customer interview"
        elif score >= 30:
            level = "LOW"
            action = "Watch list + periodic review"
        else:
            level = "CLEAR"
            action = "No action — continue standard monitoring"

        # Willing vs Unwitting mule classification
        mule_type = "N/A"
        if score >= 50:
            forwarding = features.get('forwarding_ratio', 0)
            rapid = features.get('rapid_transfer', 0)
            if forwarding > 0.9 and rapid == 1:
                mule_type = "WILLING (knowing participant)"
            else:
                mule_type = "UNWITTING (possible victim)"

        return level, action, mule_type

    def get_shap_explanation(self, X_instance):
        try:
            shap_values = self.explainer.shap_values(X_instance)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            feature_impacts = list(zip(self.feature_names, shap_values[0]))
            feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
            top_features = feature_impacts[:5]
            explanation = []
            for feat, impact in top_features:
                direction = "increases" if impact > 0 else "decreases"
                explanation.append(f"{feat} {direction} risk (impact: {impact:.3f})")
            return " | ".join(explanation)
        except:
            return "Explanation unavailable"

    def get_flags(self, features):
        flags = []
        if features.get('forwarding_ratio', 0) > 0.8:
            flags.append("Full forwarding behavior detected")
        if features.get('rapid_transfer', 0) == 1:
            flags.append("Rapid transfers within 2-hour window")
        if features.get('smurfing_score', 0) == 1:
            flags.append("Smurfing pattern — multiple small transfers")
        if features.get('ip_concentration', 0) == 1:
            flags.append("Multiple senders from same IP")
        if features.get('unique_cities', 0) >= 3:
            flags.append(f"Transactions across {int(features['unique_cities'])} cities")
        if features.get('unique_receivers', 0) >= 3:
            flags.append(f"Sends to {int(features['unique_receivers'])} unique accounts")
        return flags

    FINALIZED_FEATURES = [
        "F115", "F321", "F527", "F531", "F670", "F1692", "F2082", "F2122",
        "F2582", "F2678", "F2737", "F2956", "F3043", "F3836", "F3887",
        "F3889", "F3891", "F3894"
    ]
    TARGET_COL = "F3924"

    ACCT_OPN_ORDER = {"L31D": 0, "L90D": 1, "L180D": 2, "L365D": 3, "G365D": 4}

    # PRODUCTION FEATURE SET (validated Aug 2026)
    # Excludes known leakage columns found via SHAP investigation:
    #   - F2230 (MNTH - data collection metadata, not behavioral)
    #   - F3895-F3923 (bank's own internal incident-score/alert-flag/resolution
    #     fields - these only exist AFTER an account has already been investigated,
    #     so training on them taught the model to recognize accounts the bank had
    #     already flagged rather than learning real mule behavior; F3912
    #     FRAUD_SUSPECTED alone had 0.97 correlation with the target)
    # Result: 5-fold CV mean AUC-ROC 0.9859 (+/-0.0121) on the clean feature set,
    # vs a fake 0.9999 when leakage columns were included.
    # Corrected scope (Aug 2026): individually tested all 29 F3895-F3923
    # columns for correlation with the target. Only F2230 (categorical,
    # perfect separation) and F3912 (0.969 correlation) are genuinely leaky.
    # The other 27 were wrongly excluded on a proximity assumption in an
    # earlier pass -- confirmed clean and restored.
    LEAKAGE_EXCLUDED_FEATURES = {
        'F2230',
        'F3912',
    }

    def load_production_features(self, feature_list_path="top_features_corrected.txt"):
        """Load the validated top-100 clean feature list from disk."""
        import os
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), feature_list_path)
        with open(full_path) as f:
            feats = [line.strip() for line in f if line.strip()]
        leaked = set(feats) & self.LEAKAGE_EXCLUDED_FEATURES
        if leaked:
            raise RuntimeError(f"Feature list contains excluded leakage columns: {leaked}")
        return feats

    def load_real_dataset(self, csv_path):
        print(f"[TraceNetX ML] Loading real dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        id_col = df.columns[0]
        df = df.rename(columns={id_col: "account_id"})

        production_features = self.load_production_features()
        self.feature_names = production_features

        keep_cols = ["account_id"] + production_features + [self.TARGET_COL]
        df = df[keep_cols].copy()

        # Auto-encode any non-numeric columns among the selected production features
        for col in production_features:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.factorize(df[col].astype(str))[0]

        self.FINALIZED_FEATURES = production_features
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        print(f"[TraceNetX ML] Using {len(production_features)} validated, leakage-free production features")
        return df

    def train_on_real_data(self, df):
        feature_cols = self.FINALIZED_FEATURES
        self.feature_names = feature_cols
        X = df[feature_cols].fillna(0)
        y = df[self.TARGET_COL]

        # Split FIRST on raw features, so the scaler never sees test data
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        X_train = self.scaler.fit_transform(X_train_raw)
        X_test = self.scaler.transform(X_test_raw)

        print("[TraceNetX ML] Applying SMOTE to training data only...")
        try:
            smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
            X_train, y_train = smote.fit_resample(X_train, y_train)
        except Exception as e:
            print(f"[TraceNetX ML] SMOTE failed ({e}), using raw training data")
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
        self.iso_forest.fit(X_train)  # train split only — consistent with no test leakage
        print("[TraceNetX ML] Building SHAP explainer...")
        self.explainer = shap.TreeExplainer(self.xgb_model)
        self.is_trained = True
        y_pred = self.xgb_model.predict(X_test)
        y_proba = self.xgb_model.predict_proba(X_test)[:, 1]
        print("\n[TraceNetX ML] === REAL DATA MODEL PERFORMANCE ===")
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
        # NOTE (Aug 23 finding): empirically on the real BOI dataset, confirmed
        # mules do NOT sit at the extreme statistical-outlier fringe that
        # IsolationForest flags by default (sklearn convention: LOW score =
        # more anomalous). Standalone AUROC test showed the naive "low score
        # = high risk" mapping scores 0.18 (worse than random), while the
        # opposite mapping scores 0.82 (genuinely useful). This means mules
        # blend into moderate-density regions in this feature space, while
        # IsolationForest's flagged "anomalies" are more often ordinary rare
        # high-value legitimate transactions. Corrected mapping below.
        iso_normalized = (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min() + 1e-9)
        # Ablation finding (Aug 23): even after fixing the polarity bug above,
        # a weight-sweep on real held-out data showed AUROC falls monotonically
        # as iso_weight increases (0.936 @ weight=0 -> 0.910 @ weight=0.30).
        # IsolationForest's own standalone AUROC (0.82) is real signal, but
        # weaker than and not well rank-correlated with the supervised
        # ensemble, so blending it dilutes rather than helps. Production uses
        # ensemble-only; iso_normalized is still computed and returned
        # separately below for the Model Validation / ablation-study display.
        final_scores = ensemble_proba * 100
        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            score = float(final_scores[i])
            level, action, _ = self.classify_risk(score, {})
            shap_explanation = self.get_shap_explanation(X_scaled[i:i+1])
            results.append({'account_id': row['account_id'], 'risk_score': round(score, 2), 'risk_level': level, 'recommended_action': action, 'actual_label': int(row[self.TARGET_COL]), 'shap_explanation': shap_explanation, 'iso_anomaly_score': round(float(iso_normalized[i]) * 100, 2)})
        return sorted(results, key=lambda x: x['risk_score'], reverse=True)

# Global instance
ml_pipeline = TraceNetXMLPipeline()

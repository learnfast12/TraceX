path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

old_block_start = "    FINALIZED_FEATURES = ["
old_block_end = "    TARGET_COL = \"F3924\""

start_idx = content.find(old_block_start)
end_idx = content.find(old_block_end) + len(old_block_end)

if start_idx == -1 or end_idx == -1:
    raise RuntimeError("Could not locate FINALIZED_FEATURES/TARGET_COL block to replace.")

new_block = '''    # PRODUCTION FEATURE SET (validated Aug 2026)
    # Selected via SHAP-guided importance ranking across all 3,893 clean candidate
    # features in DataSet.csv, AFTER excluding known leakage columns:
    #   - F2230 (MNTH - data collection metadata, not behavioral)
    #   - F3895-F3923 (bank's own internal incident-score / alert-flag / resolution
    #     -status fields - these only exist AFTER an account has already been
    #     investigated, so training on them taught the model to recognize accounts
    #     the bank had already flagged rather than learning real mule behavior;
    #     F3912 FRAUD_SUSPECTED alone had 0.97 correlation with the target)
    # Result: 5-fold CV mean AUC-ROC 0.9859 (+/-0.0121) on the clean feature set,
    # vs a fake 0.9999 when leakage columns were included.
    LEAKAGE_EXCLUDED_FEATURES = {
        'F2230',
        'F3895', 'F3896', 'F3897', 'F3898', 'F3899',
        'F3900', 'F3901', 'F3902', 'F3903', 'F3904', 'F3905', 'F3906', 'F3907',
        'F3908', 'F3909', 'F3910', 'F3911', 'F3912', 'F3913', 'F3914', 'F3915',
        'F3916', 'F3917', 'F3918', 'F3919', 'F3920', 'F3921', 'F3922', 'F3923',
    }

    @classmethod
    def load_production_features(cls, feature_list_path="top_100_features_clean.txt"):
        """Load the validated top-100 clean feature list from disk."""
        import os
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), feature_list_path)
        with open(full_path) as f:
            feats = [line.strip() for line in f if line.strip()]
        leaked = set(feats) & cls.LEAKAGE_EXCLUDED_FEATURES
        if leaked:
            raise RuntimeError(f"Feature list contains excluded leakage columns: {leaked}")
        return feats

    TARGET_COL = "F3924"'''

content = content[:start_idx] + new_block + content[end_idx:]

old_load = '''    def load_real_dataset(self, csv_path):
        print(f"[TraceNetX ML] Loading real dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        id_col = df.columns[0]
        df = df.rename(columns={id_col: "account_id"})
        keep_cols = ["account_id"] + self.FINALIZED_FEATURES + [self.TARGET_COL]
        df = df[keep_cols].copy()
        # F3889 (ACCT_OPN_DAYS): ordinal bucket -> integer
        df["F3889"] = df["F3889"].map(self.ACCT_OPN_ORDER)
        # F3891 (CUST_OCCP): categorical -> one-hot, replace in feature list
        occp_dummies = pd.get_dummies(df["F3891"], prefix="OCCP").astype(int)
        df = pd.concat([df.drop(columns=["F3891"]), occp_dummies], axis=1)
        self.FINALIZED_FEATURES = [c for c in self.FINALIZED_FEATURES if c != "F3891"] + list(occp_dummies.columns)
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        print(f"[TraceNetX ML] Final feature count after encoding: {len(self.FINALIZED_FEATURES)}")
        return df'''

new_load = '''    def load_real_dataset(self, csv_path):
        print(f"[TraceNetX ML] Loading real dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        id_col = df.columns[0]
        df = df.rename(columns={id_col: "account_id"})

        production_features = self.load_production_features()
        self.feature_names = production_features

        keep_cols = ["account_id"] + production_features + [self.TARGET_COL]
        df = df[keep_cols].copy()

        # Auto-encode any categorical columns among the selected features
        for col in production_features:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.factorize(df[col].astype(str))[0]

        self.FINALIZED_FEATURES = production_features
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        print(f"[TraceNetX ML] Using {len(production_features)} validated, leakage-free production features")
        return df'''

if old_load not in content:
    raise RuntimeError("Could not find load_real_dataset to update — check file state.")
content = content.replace(old_load, new_load)

with open(path_backend, "w") as f:
    f.write(content)

print("ml_pipeline.py updated to production feature set.")
print("Copy top_100_features_clean.txt into backend/ (already there from last run).")

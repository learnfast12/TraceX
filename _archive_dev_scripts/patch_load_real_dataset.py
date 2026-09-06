path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

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

        # Auto-encode any non-numeric columns among the selected production features
        for col in production_features:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.factorize(df[col].astype(str))[0]

        self.FINALIZED_FEATURES = production_features
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        print(f"[TraceNetX ML] Using {len(production_features)} validated, leakage-free production features")
        return df'''

count = content.count(old_load)
if count == 0:
    raise RuntimeError("Still no match — need to inspect file for hidden whitespace/tab differences.")
if count > 1:
    raise RuntimeError(f"Matched {count} times — old_load isn't unique, refusing to patch blindly.")

content = content.replace(old_load, new_load)

with open(path_backend, "w") as f:
    f.write(content)

print("Patched successfully — load_real_dataset now uses the clean production feature set.")

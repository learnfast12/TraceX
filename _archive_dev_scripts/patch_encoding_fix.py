path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

old = '''    def load_real_dataset(self, csv_path):
        print(f"[TraceNetX ML] Loading real dataset from {csv_path}...")
        df = pd.read_csv(csv_path)
        id_col = df.columns[0]
        df = df.rename(columns={id_col: "account_id"})
        keep_cols = ["account_id"] + self.FINALIZED_FEATURES + [self.TARGET_COL]
        df = df[keep_cols]
        print(f"[TraceNetX ML] Loaded {len(df)} accounts, {int(df[self.TARGET_COL].sum())} confirmed mules ({df[self.TARGET_COL].mean()*100:.2f}%)")
        return df'''

new = '''    ACCT_OPN_ORDER = {"L31D": 0, "L90D": 1, "L180D": 2, "L365D": 3, "G365D": 4}

    def load_real_dataset(self, csv_path):
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

if old not in content:
    raise RuntimeError("Could not find load_real_dataset to patch — may already be modified.")

content = content.replace(old, new)
with open(path_backend, "w") as f:
    f.write(content)
print("Encoding fix applied.")

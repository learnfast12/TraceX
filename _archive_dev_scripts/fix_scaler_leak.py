path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

old = '''        X = df[feature_cols].fillna(0)
        y = df[self.TARGET_COL]
        X_scaled = self.scaler.fit_transform(X)

        # Split FIRST, so test set stays real (no synthetic leakage into evaluation)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )'''

new = '''        X = df[feature_cols].fillna(0)
        y = df[self.TARGET_COL]

        # Split FIRST on raw features, so the scaler never sees test data
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        X_train = self.scaler.fit_transform(X_train_raw)
        X_test = self.scaler.transform(X_test_raw)'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected exactly 1 match, found {count} — inspect file before patching.")
content = content.replace(old, new)

with open(path_backend, "w") as f:
    f.write(content)
print("Scaler leak fixed — scaler now fits on train split only.")

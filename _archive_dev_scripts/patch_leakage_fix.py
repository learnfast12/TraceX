path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

old = '''        X_scaled = self.scaler.fit_transform(X)
        print("[TraceNetX ML] Applying SMOTE...")
        try:
            smote = SMOTE(random_state=42)
            X_res, y_res = smote.fit_resample(X_scaled, y)
        except Exception as e:
            print(f"[TraceNetX ML] SMOTE failed ({e}), using raw data")
            X_res, y_res = X_scaled, y
        X_train, X_test, y_train, y_test = train_test_split(X_res, y_res, test_size=0.2, random_state=42, stratify=y_res)'''

new = '''        X_scaled = self.scaler.fit_transform(X)

        # Split FIRST, so test set stays real (no synthetic leakage into evaluation)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )

        print("[TraceNetX ML] Applying SMOTE to training data only...")
        try:
            smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
            X_train, y_train = smote.fit_resample(X_train, y_train)
        except Exception as e:
            print(f"[TraceNetX ML] SMOTE failed ({e}), using raw training data")'''

if old not in content:
    raise RuntimeError("Pattern not found — pipeline may already differ from expected.")

content = content.replace(old, new)
with open(path_backend, "w") as f:
    f.write(content)
print("Leakage fix applied — SMOTE now train-only, test set is real/untouched.")

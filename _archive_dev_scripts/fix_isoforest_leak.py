path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

old = '''        print("[TraceNetX ML] Training Isolation Forest...")
        self.iso_forest = IsolationForest(contamination=0.01, random_state=42)
        self.iso_forest.fit(X_scaled)'''

new = '''        print("[TraceNetX ML] Training Isolation Forest...")
        self.iso_forest = IsolationForest(contamination=0.01, random_state=42)
        self.iso_forest.fit(X_train)  # train split only — consistent with no test leakage'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected exactly 1 match, found {count} — inspect file before patching.")
content = content.replace(old, new)

with open(path_backend, "w") as f:
    f.write(content)
print("Isolation Forest now fit on X_train only — X_scaled reference removed.")

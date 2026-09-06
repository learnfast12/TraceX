import pandas as pd
import numpy as np

csv_path = "/home/x0_shravan_0x/Downloads/DataSet.csv"
df = pd.read_csv(csv_path)

target_col = "F3924"
suspect_cols = ["F2230"] + [f"F{n}" for n in range(3895, 3924)]

print(f"Checking correlation with {target_col} for {len(suspect_cols)} currently-excluded columns...\n")

results = []
for col in suspect_cols:
    if col not in df.columns:
        print(f"{col}: NOT FOUND in dataset")
        continue
    series = df[col]

    if pd.api.types.is_numeric_dtype(series):
        corr = series.corr(df[target_col])
        results.append((col, "numeric", corr))
    else:
        numeric = pd.to_numeric(series, errors='coerce')
        if numeric.notna().sum() / len(numeric) > 0.9:
            corr = numeric.corr(df[target_col])
            results.append((col, "numeric", corr))
        else:
            ct = pd.crosstab(series, df[target_col])
            correct = ct.max(axis=1).sum()
            acc = correct / len(df)
            results.append((col, "categorical", acc))

print(f"{'Column':<10} {'Type':<12} {'Corr/Accuracy':<15} {'Flag'}")
print("-" * 55)
for col, kind, val in results:
    if kind == "numeric":
        flag = "LEAK (>0.90)" if abs(val) > 0.90 else ("watch" if abs(val) > 0.5 else "clean")
        print(f"{col:<10} {kind:<12} {val:<15.4f} {flag}")
    else:
        flag = "LEAK (>=0.98 acc)" if val >= 0.98 else ("watch" if val > 0.9 else "clean")
        print(f"{col:<10} {kind:<12} {val:<15.4f} {flag}")

import pandas as pd

df = pd.read_csv('/home/x0_shravan_0x/Downloads/DataSet.csv')
target_col = "F3924"
id_col = df.columns[0]
correctly_excluded = {"F2230", "F3912"}

all_features = [c for c in df.columns if c not in (id_col, target_col) and c not in correctly_excluded]
numeric_features = [c for c in all_features if pd.api.types.is_numeric_dtype(df[c])]

path = "/home/x0_shravan_0x/Tracenetx/backend/top_features_corrected.txt"
with open(path, "w") as f:
    for feat in numeric_features:
        f.write(feat + "\n")

print(f"Wrote {len(numeric_features)} features to {path}")

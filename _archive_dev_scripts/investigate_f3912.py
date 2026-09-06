import pandas as pd

# 1. What does the bank's data dictionary say F3912 actually is?
dd = pd.read_excel('/home/x0_shravan_0x/Downloads/Description_1_.xlsx', sheet_name='Data_Dicitionary')
row = dd[dd['Feature'] == 'F3912']
print("=== F3912 definition from bank data dictionary ===")
print(row.to_string(index=False))

# 2. How does F3912 relate to the target?
df = pd.read_csv('/home/x0_shravan_0x/Downloads/DataSet.csv')
print("\n=== F3912 value distribution by label ===")
print(df.groupby('F3924')['F3912'].describe())

print("\n=== Sample F3912 values for mules (label=1) ===")
print(df[df['F3924'] == 1]['F3912'].head(20).tolist())

print("\n=== Sample F3912 values for non-mules (label=0) ===")
print(df[df['F3924'] == 0]['F3912'].head(20).tolist())

print("\n=== Correlation with target ===")
print(df['F3912'].corr(df['F3924']))

# 3. Also check the two next-highest features for the same issue
for feat in ['F2230', 'F1165']:
    print(f"\n=== {feat} definition ===")
    r = dd[dd['Feature'] == feat]
    print(r.to_string(index=False))
    print(f"{feat} correlation with target:", df[feat].corr(df['F3924']))

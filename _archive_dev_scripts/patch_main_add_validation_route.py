path_main = "/home/x0_shravan_0x/Tracenetx/backend/main.py"
with open(path_main, "r") as f:
    content = f.read()

# 1. Add the import
old_import = "from response_engine import response_engine\nimport pandas as pd"
new_import = "from response_engine import response_engine\nfrom real_validation import run_real_validation\nimport pandas as pd"
if content.count(old_import) != 1:
    raise RuntimeError("Import anchor not unique or not found — inspect file.")
content = content.replace(old_import, new_import)

# 2. Add the new route, right before /intelligence/full
anchor = '@app.get("/intelligence/full")'
if content.count(anchor) != 1:
    raise RuntimeError("Route anchor not unique or not found — inspect file.")

new_route = '''@app.get("/ml/real-data-validation")
def ml_real_data_validation():
    """
    Real Bank of India dataset validation — leak-free stratified 5-fold CV
    results, SHAP feature importance on the real 100-feature production set,
    and the label-leakage discovery narrative. Independent from the
    interactive demo network (transactions.csv) — see module docstring.
    """
    return run_real_validation()


''' + anchor

content = content.replace(anchor, new_route)

with open(path_main, "w") as f:
    f.write(content)
print("main.py patched — new /ml/real-data-validation route added.")

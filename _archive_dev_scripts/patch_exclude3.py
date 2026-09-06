path = "/home/x0_shravan_0x/feature_selection_clean.py"
with open(path, "r") as f:
    content = f.read()

old = "    'F3897',  # CNT_INC_SCR_GT650 - internal incident/risk score, not raw behavior\n}"
new = "    'F3895', 'F3896', 'F3897',  # MIN/MAX_INC_SCORE + CNT_INC_SCR_GT650 - internal incident/risk score, not raw behavior\n}"

if old not in content:
    raise RuntimeError("Pattern not found.")
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("F3895 and F3896 added to exclusion list. Final feature set locked.")

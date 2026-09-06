path = "/home/x0_shravan_0x/feature_selection_clean.py"
with open(path, "r") as f:
    content = f.read()

old = "'F3919', 'F3920', 'F3921', 'F3922', 'F3923',  # alert counts - already-flagged history\n}"
new = "'F3919', 'F3920', 'F3921', 'F3922', 'F3923',  # alert counts - already-flagged history\n    'F3897',  # CNT_INC_SCR_GT650 - internal incident/risk score, not raw behavior\n}"

if old not in content:
    raise RuntimeError("Pattern not found.")
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("F3897 added to exclusion list.")

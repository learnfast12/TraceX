path = "/home/x0_shravan_0x/feature_selection_clean.py"
with open(path, "r") as f:
    content = f.read()

old = """EXCLUDE = {
    'F3912',  # FRAUD_SUSPECTED - resolution status flag, correlation 0.97 with target = LEAKAGE
    'F2230',  # MNTH - month of data collection, not a behavioral feature
}"""

new = """EXCLUDE = {
    'F2230',  # MNTH - month of data collection, not a behavioral feature
    'F3898', 'F3899',  # MIN/MAX_RESOLVE_DAYS - only exists after investigation closed
    'F3900', 'F3901', 'F3902', 'F3903', 'F3904', 'F3905', 'F3906', 'F3907',
    'F3908', 'F3909', 'F3910', 'F3911',  # alert description flags - alert already fired
    'F3912', 'F3913', 'F3914', 'F3915',  # resolution status flags - investigation outcome
    'F3916', 'F3917', 'F3918',  # L1/L2/L3_FLG - pre-existing risk tier from bank's own system
    'F3919', 'F3920', 'F3921', 'F3922', 'F3923',  # alert counts - already-flagged history
}"""

if old not in content:
    raise RuntimeError("Pattern not found, check file.")
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("Exclusion list updated - full alert-system block now excluded.")

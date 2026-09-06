path = "/home/x0_shravan_0x/Tracenetx/backend/lstm_temporal.py"
with open(path, "r") as f:
    content = f.read()

old = "lstm_detector = LSTMTemporalDetector()"
new = "lstm_detector = TemporalPatternEngine()"

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count} — check file manually")
content = content.replace(old, new)

with open(path, "w") as f:
    f.write(content)
print("Fixed: instantiation now uses TemporalPatternEngine")

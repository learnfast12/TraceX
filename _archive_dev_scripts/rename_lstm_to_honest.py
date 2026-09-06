import re

# --- Backend: lstm_temporal.py ---
path_backend = "/home/x0_shravan_0x/Tracenetx/backend/lstm_temporal.py"
with open(path_backend, "r") as f:
    content = f.read()

content = content.replace(
    "class LSTMTemporalDetector:",
    "class TemporalPatternEngine:\n    \"\"\"\n    Rule-based behavioral sequence detector for mule account lifecycle patterns.\n    Not a trained neural network — deterministic threshold/window logic over\n    each account's transaction timeline (dormant reactivation, delayed\n    layering, velocity spikes, smurfing, rapid forwarding).\n    \"\"\""
)

with open(path_backend, "w") as f:
    f.write(content)
print("[lstm_temporal.py] class renamed to TemporalPatternEngine")

# --- Backend: main.py — update the import/instance name ---
path_main = "/home/x0_shravan_0x/Tracenetx/backend/main.py"
with open(path_main, "r") as f:
    content = f.read()

count = content.count("from lstm_temporal import lstm_detector")
if count == 1:
    content = content.replace(
        "from lstm_temporal import lstm_detector",
        "from lstm_temporal import lstm_detector  # TemporalPatternEngine instance — rule-based, not a trained LSTM"
    )
    with open(path_main, "w") as f:
        f.write(content)
    print("[main.py] import comment updated (kept variable name lstm_detector to avoid breaking other references)")
else:
    print(f"[main.py] import line not found in expected form (count={count}) — skipped, no changes made")

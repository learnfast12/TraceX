path = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path, "r") as f:
    content = f.read()

old = '''            # Rapid transfer detection
            rapid_transfer = 0
            if len(outgoing) >= 2:
                try:
                    times = pd.to_datetime(outgoing['timestamp']).sort_values()
                    span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 3600
                    rapid_transfer = 1 if span <= 2 else 0
                except:
                    pass'''

new = '''            # Rapid transfer detection — two real patterns, not just one:
            # (1) multiple outgoing transfers clustered within a 2hr window
            #     (staggered layering), or
            # (2) a single-hop pass-through: funds forwarded within 2hrs of
            #     being received (e.g. one big incoming payment immediately
            #     dumped onward) — this pattern was previously invisible
            #     because it requires only ONE outgoing transaction, which
            #     failed the old len(outgoing) >= 2 gate entirely
            rapid_transfer = 0
            if len(outgoing) >= 2:
                try:
                    times = pd.to_datetime(outgoing['timestamp']).sort_values()
                    span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 3600
                    if span <= 2:
                        rapid_transfer = 1
                except:
                    pass
            if rapid_transfer == 0 and len(outgoing) >= 1 and len(incoming) >= 1:
                try:
                    last_in = pd.to_datetime(incoming['timestamp']).max()
                    first_out = pd.to_datetime(outgoing['timestamp']).min()
                    latency = (first_out - last_in).total_seconds() / 3600
                    if 0 <= latency <= 2:
                        rapid_transfer = 1
                except:
                    pass'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count}")
content = content.replace(old, new)

with open(path, "w") as f:
    f.write(content)
print("rapid_transfer now also detects single-hop pass-through (receive-to-forward latency).")

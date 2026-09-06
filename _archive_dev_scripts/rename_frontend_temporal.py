path_app = "/home/x0_shravan_0x/Tracenetx/frontend/tracenetx-ui/src/App.js"
with open(path_app, "r") as f:
    content = f.read()

old = '<p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Dormant reactivation · Delayed layering · Velocity spikes · Smurfing · Rapid forwarding</p>'
new = '<p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Rule-based sequence detection — Dormant reactivation · Delayed layering · Velocity spikes · Smurfing · Rapid forwarding</p>'

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count}")
content = content.replace(old, new)

with open(path_app, "w") as f:
    f.write(content)
print("Frontend Temporal tab subtitle updated.")

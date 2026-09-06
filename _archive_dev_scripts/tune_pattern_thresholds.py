path_gi = "/home/x0_shravan_0x/Tracenetx/backend/graph_intelligence.py"
with open(path_gi, "r") as f:
    content = f.read()

# Tighten hawala: require 3+ independent senders AND near-total forwarding (>=0.95)
# to distinguish the specific hawala signature from generic mule pass-through
old_hawala = '''                # Behavioral signal only: receives from 2+ independent senders AND
                # forwards 70%+ of what it took in — the actual hawala broker
                # signature (rapid pass-through), not a name match on the account ID
                if record["unique_senders"] >= 2 and ratio >= 0.7:'''
new_hawala = '''                # Behavioral signal only: receives from 3+ independent senders AND
                # forwards 95%+ of what it took in — near-total pass-through from
                # many sources is the actual hawala broker signature; a looser
                # threshold also catches ordinary mules forwarding most of one
                # inbound payment, which is a different (weaker) signal
                if record["unique_senders"] >= 3 and ratio >= 0.95:'''

count = content.count(old_hawala)
if count != 1:
    raise RuntimeError(f"[hawala] expected 1 match, found {count}")
content = content.replace(old_hawala, new_hawala)
print("[hawala] tightened to senders>=3, ratio>=0.95")

# Loosen shell slightly: round_ratio >= 0.5 (half or more round-number txns) instead of 0.6
old_shell = '''                if record["txn_count"] >= 2 and round_ratio >= 0.6 and sender_concentration >= 2:'''
new_shell = '''                if record["txn_count"] >= 2 and round_ratio >= 0.5 and sender_concentration >= 2:'''

count = content.count(old_shell)
if count != 1:
    raise RuntimeError(f"[shell] expected 1 match, found {count}")
content = content.replace(old_shell, new_shell)
print("[shell] loosened to round_ratio>=0.5")

with open(path_gi, "w") as f:
    f.write(content)

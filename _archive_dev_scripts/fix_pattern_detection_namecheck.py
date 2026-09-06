path_gi = "/home/x0_shravan_0x/Tracenetx/backend/graph_intelligence.py"
with open(path_gi, "r") as f:
    content = f.read()

# --- Fix 1: hawala_broker_detection — remove name-check, use forwarding ratio only ---
old_hawala = '''                if record["unique_senders"] >= 2 and ("HAWALA" in record["account"].upper() or ratio >= 0.7):'''
new_hawala = '''                # Behavioral signal only: receives from 2+ independent senders AND
                # forwards 70%+ of what it took in — the actual hawala broker
                # signature (rapid pass-through), not a name match on the account ID
                if record["unique_senders"] >= 2 and ratio >= 0.7:'''

count = content.count(old_hawala)
if count != 1:
    raise RuntimeError(f"[hawala] expected 1 match, found {count}")
content = content.replace(old_hawala, new_hawala)
print("[hawala_broker_detection] name-check removed, behavioral-only threshold retained")

# --- Fix 2: shell_company_detection — remove name-check, use round-amount + sender concentration ---
old_shell = '''                if record["txn_count"] >= 2 and "SHELL" in record["account"].upper():'''
new_shell = '''                # Behavioral signal only: majority of inbound amounts are suspiciously
                # round (multiples of 10,000) AND funds arrive from multiple senders in
                # bursts — the actual shell-company pattern, not a name match
                if record["txn_count"] >= 2 and round_ratio >= 0.6 and sender_concentration >= 2:'''

count = content.count(old_shell)
if count != 1:
    raise RuntimeError(f"[shell] expected 1 match, found {count}")
content = content.replace(old_shell, new_shell)
print("[shell_company_detection] name-check removed, behavioral-only threshold retained")

with open(path_gi, "w") as f:
    f.write(content)
print("\\nBoth fixes applied.")

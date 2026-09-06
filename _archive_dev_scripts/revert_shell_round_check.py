path_gi = "/home/x0_shravan_0x/Tracenetx/backend/graph_intelligence.py"
with open(path_gi, "r") as f:
    content = f.read()

old = '''                # Round to nearest 1,000 rather than 10,000 — real shell company
                # payments (e.g. 57000, 58000) are typically round to the nearest
                # thousand, not the nearest ten-thousand
                round_count = sum(1 for a in amounts if a % 1000 == 0)'''
new = '''                round_count = sum(1 for a in amounts if a % 10000 == 0)'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count}")
content = content.replace(old, new)

with open(path_gi, "w") as f:
    f.write(content)
print("Reverted shell round-amount check to nearest 10,000.")

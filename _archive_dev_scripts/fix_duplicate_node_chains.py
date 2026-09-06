path_gi = "/home/x0_shravan_0x/Tracenetx/backend/graph_intelligence.py"
with open(path_gi, "r") as f:
    content = f.read()

old = '''            chains = []
            for record in result:
                chains.append({
                    "chain": record["chain"],
                    "amounts": record["amounts"],
                    "hops": record["hops"],
                    "entry_point": record["chain"][0],
                    "exit_point": record["chain"][-1]
                })'''

new = '''            chains = []
            for record in result:
                chain_nodes = record["chain"]
                # Skip non-simple paths where a node is revisited — a real fund
                # flow cannot pass through the same account twice in one link
                # of custody; this is a Cypher variable-length-path artifact,
                # not a real transaction pattern.
                if len(chain_nodes) != len(set(chain_nodes)):
                    continue
                chains.append({
                    "chain": chain_nodes,
                    "amounts": record["amounts"],
                    "hops": record["hops"],
                    "entry_point": chain_nodes[0],
                    "exit_point": chain_nodes[-1]
                })'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count} — inspect file before patching.")
content = content.replace(old, new)

with open(path_gi, "w") as f:
    f.write(content)
print("Patched reverse_chain_analysis to filter out non-simple (repeated-node) paths.")

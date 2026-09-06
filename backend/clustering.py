"""
TRACE-X — clustering.py
Deterministic entity resolution: Union-Find over common-input-ownership +
change-address heuristic. This runs BEFORE any ML and should resolve the
majority of the wallet graph into entity clusters on its own.
"""

import csv
import json
from collections import defaultdict


class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            return x
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def groups(self):
        out = defaultdict(set)
        for x in self.parent:
            out[self.find(x)].add(x)
        return dict(out)


def load_transactions(tx_csv_path):
    """Group rows by txid -> {inputs: [(wallet, amount)], outputs: [(wallet, amount, timestamp)]}"""
    tx_map = defaultdict(lambda: {"inputs": [], "outputs": []})
    with open(tx_csv_path) as f:
        for row in csv.DictReader(f):
            entry = (row["wallet"], float(row["amount"]), row["timestamp"])
            if row["role"] == "input":
                tx_map[row["txid"]]["inputs"].append(entry)
            else:
                tx_map[row["txid"]]["outputs"].append(entry)
    return tx_map


def compute_first_seen(tx_map):
    """Earliest timestamp at which each wallet appears anywhere (input or output)."""
    first_seen = {}
    for txid, data in tx_map.items():
        for wallet, amount, ts in data["inputs"] + data["outputs"]:
            if wallet not in first_seen or ts < first_seen[wallet]:
                first_seen[wallet] = ts
    return first_seen


def cluster_entities(tx_csv_path, round_amount_tolerance=1e-6):
    tx_map = load_transactions(tx_csv_path)
    first_seen = compute_first_seen(tx_map)
    uf = UnionFind()

    reasons = defaultdict(list)  # (wallet_a, wallet_b) -> reason strings, for audit trail

    for txid, data in tx_map.items():
        input_wallets = [w for w, amt, ts in data["inputs"]]

        # --- Rule 1: common-input-ownership ---
        # every input wallet on the same tx must be co-signed by the same entity
        for i in range(1, len(input_wallets)):
            uf.union(input_wallets[0], input_wallets[i])
            reasons[(input_wallets[0], input_wallets[i])].append(
                f"common_input:{txid}")

        if not input_wallets:
            continue

        # --- Rule 2: change-address heuristic ---
        # only meaningful for the classic 2-output payment+change shape
        outputs = data["outputs"]
        if len(outputs) == 2:
            (w1, a1, t1), (w2, a2, t2) = outputs
            for change_wallet, change_amount, change_ts in [(w1, a1, t1), (w2, a2, t2)]:
                is_fresh = first_seen.get(change_wallet) == change_ts
                is_nonround = abs(change_amount - round(change_amount, 2)) > round_amount_tolerance
                if is_fresh and is_nonround:
                    uf.union(input_wallets[0], change_wallet)
                    reasons[(input_wallets[0], change_wallet)].append(
                        f"change_address:{txid}")

    clusters = uf.groups()
    return clusters, reasons


def evaluate_against_ground_truth(clusters, ground_truth_path):
    """
    Purity: for each computed cluster, what fraction of its wallets share the
    same true entity_id (precision-like — are we over-merging different entities?).
    Recall: for each true entity with >=2 wallets, were all its wallets placed
    in the same computed cluster (are we under-merging / missing links?).
    """
    gt = json.load(open(ground_truth_path))
    wallet_to_true_entity = {}
    for g in gt:
        for w in g["wallets"]:
            wallet_to_true_entity[w] = g["entity_id"]

    # purity
    purities = []
    for cluster_wallets in clusters.values():
        true_ids = [wallet_to_true_entity.get(w) for w in cluster_wallets if w in wallet_to_true_entity]
        if not true_ids:
            continue
        most_common = max(set(true_ids), key=true_ids.count)
        purity = true_ids.count(most_common) / len(true_ids)
        purities.append((purity, len(cluster_wallets)))

    weighted_purity = sum(p * n for p, n in purities) / sum(n for _, n in purities) if purities else 0

    # recall: multi-wallet entities only
    wallet_to_cluster_root = {}
    for root, wallets in clusters.items():
        for w in wallets:
            wallet_to_cluster_root[w] = root

    recalls = []
    for g in gt:
        wallets = [w for w in g["wallets"] if w in wallet_to_cluster_root]
        if len(wallets) < 2:
            continue
        roots = set(wallet_to_cluster_root[w] for w in wallets)
        recalls.append(1.0 if len(roots) == 1 else 0.0)

    recall_rate = sum(recalls) / len(recalls) if recalls else 0

    return {
        "num_clusters": len(clusters),
        "weighted_purity": round(weighted_purity, 4),
        "multi_wallet_entity_recall": round(recall_rate, 4),
        "multi_wallet_entities_checked": len(recalls),
    }


if __name__ == "__main__":
    clusters, reasons = cluster_entities("dataset/output/bitcoin_transactions.csv")
    metrics = evaluate_against_ground_truth(clusters, "dataset/output/ground_truth.json")
    print(json.dumps(metrics, indent=2))

    cluster_sizes = sorted((len(w) for w in clusters.values()), reverse=True)
    print(f"\nLargest 10 cluster sizes: {cluster_sizes[:10]}")
    print(f"Singleton clusters (size 1): {sum(1 for s in cluster_sizes if s == 1)}")

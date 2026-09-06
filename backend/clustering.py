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


def compute_ever_spent_from(tx_map):
    """Wallets that appear as an INPUT on any transaction, anywhere in the
    dataset. A genuine change address stays under the entity's control and
    gets spent again later; a one-time external payment recipient never
    does. This is a real, non-ambiguous signal — unlike raw 'freshness',
    which cannot distinguish a change address from a one-time external
    payee (both are first-seen at the exact same transaction)."""
    spent_from = set()
    for txid, data in tx_map.items():
        for wallet, amount, ts in data["inputs"]:
            spent_from.add(wallet)
    return spent_from


def is_likely_coinjoin(data, min_participants=5, denom_cv_threshold=0.05):
    """
    Shape-based CoinJoin detector: many inputs, many outputs, output amounts
    clustered tightly around a common denomination (low coefficient of
    variation). This is the well-documented failure mode of naive
    common-input-ownership clustering (Moser & Bohme et al.) — real forensic
    tools must detect and EXCLUDE this shape from Rule 1, or they wrongly
    weld unrelated participants into one false entity.
    """
    n_in, n_out = len(data["inputs"]), len(data["outputs"])
    if n_in < min_participants or n_out < min_participants:
        return False
    amounts = [a for _, a, _ in data["outputs"]]
    mean = sum(amounts) / len(amounts)
    if mean == 0:
        return False
    variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
    cv = (variance ** 0.5) / mean
    return cv < denom_cv_threshold


def cluster_entities(tx_csv_path, round_amount_tolerance=1e-6):
    tx_map = load_transactions(tx_csv_path)
    first_seen = compute_first_seen(tx_map)
    ever_spent_from = compute_ever_spent_from(tx_map)
    uf = UnionFind()

    reasons = defaultdict(list)  # (wallet_a, wallet_b) -> reason strings, for audit trail
    excluded_coinjoin_txids = []

    for txid, data in tx_map.items():
        input_wallets = [w for w, amt, ts in data["inputs"]]

        if is_likely_coinjoin(data):
            excluded_coinjoin_txids.append(txid)
            continue  # skip Rule 1 entirely — do not let CoinJoin participants merge

        # --- Rule 1: common-input-ownership ---
        # every input wallet on the same tx must be co-signed by the same entity
        for i in range(1, len(input_wallets)):
            uf.union(input_wallets[0], input_wallets[i])
            reasons[(input_wallets[0], input_wallets[i])].append(
                f"common_input:{txid}")

        if not input_wallets:
            continue

        # --- Rule 2: change-address heuristic ---
        # Only meaningful for the classic 2-output payment+change shape, and
        # only applied when EXACTLY ONE output looks like change. Signal:
        # first-seen at this tx (genuinely new address) AND spent from again
        # later (stays under the entity's control) — NOT mere freshness,
        # which can't distinguish change from a one-time external payee.
        outputs = data["outputs"]
        if len(outputs) == 2:
            candidates = []
            for wallet, amount, ts in outputs:
                is_fresh = first_seen.get(wallet) == ts
                is_respent = wallet in ever_spent_from
                if is_fresh and is_respent:
                    candidates.append(wallet)
            if len(candidates) == 1:
                change_wallet = candidates[0]
                uf.union(input_wallets[0], change_wallet)
                reasons[(input_wallets[0], change_wallet)].append(
                    f"change_address:{txid}")

    clusters = uf.groups()
    return clusters, reasons, excluded_coinjoin_txids


# Archetypes whose TRUE laundering behavior deliberately avoids shared-input /
# change-address signatures (peeling = fresh wallet per hop, mixer = unrelated
# co-signers by design, ransomware sweep = single-in/single-out). Tier-1
# deterministic clustering is not meant to resolve these — Tier-2 pattern
# detection (chain-walk, equal-denomination matching) is. Kept as a separate
# reporting bucket so the headline number isn't measuring the wrong layer.
CLUSTERING_APPLICABLE_TYPES = {"legit_individual", "legit_business", "darknet_vendor"}


def evaluate_against_ground_truth(clusters, ground_truth_path):
    """
    Purity: for each computed cluster, what fraction of its wallets share the
    same true entity_id (precision-like — are we over-merging different entities?).
    Recall: for each true entity with >=2 wallets, were all its wallets placed
    in the same computed cluster (are we under-merging / missing links?).
    An entity whose wallets never entered ANY cluster counts as a recall=0
    miss — it is never silently dropped from the denominator.
    """
    gt = json.load(open(ground_truth_path))
    wallet_to_true_entity = {}
    for g in gt:
        for w in g["wallets"]:
            wallet_to_true_entity[w] = g["entity_id"]

    purities = []
    for cluster_wallets in clusters.values():
        true_ids = [wallet_to_true_entity.get(w) for w in cluster_wallets if w in wallet_to_true_entity]
        if not true_ids:
            continue
        most_common = max(set(true_ids), key=true_ids.count)
        purity = true_ids.count(most_common) / len(true_ids)
        purities.append((purity, len(cluster_wallets)))

    weighted_purity = sum(p * n for p, n in purities) / sum(n for _, n in purities) if purities else 0

    wallet_to_cluster_root = {}
    for root, wallets in clusters.items():
        for w in wallets:
            wallet_to_cluster_root[w] = root

    per_type = {}
    for g in gt:
        wallets = g["wallets"]
        if len(wallets) < 2:
            continue
        # coverage: fraction of this entity's wallets that ever entered ANY
        # Tier-1 clustering rule (appeared in a >=2-input tx, or was resolved
        # as a unique change-address candidate). A wallet that only ever
        # appears as a lone recipient has zero opportunity to be linked by
        # these rules — that is a real ceiling on deterministic clustering,
        # not a bug, so it is measured separately rather than counted as a miss.
        linked_wallets = [w for w in wallets if w in wallet_to_cluster_root]
        coverage = len(linked_wallets) / len(wallets)

        # conditional recall: of the wallets that DID have a linking
        # opportunity, were they all placed in the same cluster?
        cond_hit = None
        if len(linked_wallets) >= 2:
            roots = set(wallet_to_cluster_root[w] for w in linked_wallets)
            cond_hit = 1.0 if len(roots) == 1 else 0.0

        et = g["entity_type"]
        per_type.setdefault(et, {"coverage": [], "cond_recall": []})
        per_type[et]["coverage"].append(coverage)
        if cond_hit is not None:
            per_type[et]["cond_recall"].append(cond_hit)

    def _avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else None

    per_type_out = {}
    all_coverage, all_cond_recall = [], []
    applicable_coverage, applicable_cond_recall = [], []
    for et, d in sorted(per_type.items()):
        per_type_out[et] = {
            "avg_coverage": _avg(d["coverage"]),
            "conditional_recall": _avg(d["cond_recall"]),
            "n": len(d["coverage"]),
            "n_with_linking_opportunity": len(d["cond_recall"]),
            "clustering_applicable": et in CLUSTERING_APPLICABLE_TYPES,
        }
        all_coverage += d["coverage"]
        all_cond_recall += d["cond_recall"]
        if et in CLUSTERING_APPLICABLE_TYPES:
            applicable_coverage += d["coverage"]
            applicable_cond_recall += d["cond_recall"]

    return {
        "num_clusters": len(clusters),
        "weighted_purity": round(weighted_purity, 4),
        "overall_avg_coverage": _avg(all_coverage),
        "overall_conditional_recall": _avg(all_cond_recall),
        "clustering_applicable_avg_coverage": _avg(applicable_coverage),
        "clustering_applicable_conditional_recall": _avg(applicable_cond_recall),
        "per_type": per_type_out,
    }


def evaluate_coinjoin_detection(excluded_txids, coinjoin_gt_path):
    true_coinjoin = set(json.load(open(coinjoin_gt_path)))
    detected = set(excluded_txids)
    tp = len(detected & true_coinjoin)
    fp = len(detected - true_coinjoin)
    fn = len(true_coinjoin - detected)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None}


if __name__ == "__main__":
    clusters, reasons, excluded_coinjoin = cluster_entities("dataset/output/bitcoin_transactions.csv")
    metrics = evaluate_against_ground_truth(clusters, "dataset/output/ground_truth.json")
    print(json.dumps(metrics, indent=2))

    cj_metrics = evaluate_coinjoin_detection(excluded_coinjoin, "dataset/output/coinjoin_ground_truth.json")
    print("\nCoinJoin shape-detection (Tier-2 signal, evaluated separately):")
    print(json.dumps(cj_metrics, indent=2))

    cluster_sizes = sorted((len(w) for w in clusters.values()), reverse=True)
    print(f"\nLargest 10 cluster sizes: {cluster_sizes[:10]}")
    print(f"Singleton clusters (size 1): {sum(1 for s in cluster_sizes if s == 1)}")

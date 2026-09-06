"""
TRACE-X Synthetic Dataset Generator — generator.py
Driver: reads config, instantiates entities per archetype count, runs .generate(),
exports canonical CSVs (bech32-wrapped wallet IDs) for the model pipeline, and a
separate ground_truth.json that is NEVER fed into training/feature engineering.
"""

import json
import csv
import hashlib
import os
import random

from entities import ARCHETYPES

DEFAULT_CONFIG = {
    "timespan_days": 180,
    "peel_min_hops": 6,
    "peel_max_hops": 20,
    "tor_like_ip_pool": [f"185.220.10{n}.{random.randint(1,254)}" for n in range(1, 6)],
    "ip_pool": None,  # None = fully random IPs for non-Tor archetypes
    "archetype_counts": {
        "legit_individual": 400,
        "legit_business": 25,
        "ransomware_collector": 8,
        "peeling_chain_sloppy": 15,
        "peeling_chain_careful": 12,
        "mixer_coinjoin": 6,
        "darknet_vendor": 10,
    },
    "seed": 42,
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")


def _bech32_cosmetic(wallet_id: str) -> str:
    """
    Cosmetic-only wrapper: deterministic hash of the readable internal ID into a
    bech32-LOOKING string (bc1q + hex-derived chars). NOT real bech32 encoding —
    purely for visual realism in the demo/CSV. Internal joins still happen on
    wallet_id before this is applied at export time.
    """
    h = hashlib.sha256(wallet_id.encode()).hexdigest()
    charset = "023456789acdefghjklmnpqrstuvwxyz"  # bech32 charset (no 1,b,i,o)
    out = "".join(charset[int(h[i:i+2], 16) % len(charset)] for i in range(0, 40, 2))
    return f"bc1q{out}"


def generate_dataset(config=None):
    config = config or DEFAULT_CONFIG
    random.seed(config.get("seed", 42))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_entities = []
    entity_id = 0
    for archetype_name, count in config["archetype_counts"].items():
        cls = ARCHETYPES[archetype_name]
        for _ in range(count):
            entity = cls(entity_id=f"{entity_id:05d}", config=config)
            entity.generate()
            all_entities.append(entity)
            entity_id += 1

    # _bech32_cosmetic is a pure deterministic function of wallet_id, so we
    # can wrap ANY wallet string on the fly — including external/untracked
    # counterparty wallets that never appear in an entity's own .wallets list.
    tx_rows, relay_rows, ground_truth = [], [], []

    for e in all_entities:
        for row in e.transactions:
            row = dict(row)
            row["wallet"] = _bech32_cosmetic(row["wallet"])
            tx_rows.append(row)
        for row in e.relay_events:
            relay_rows.append(row)
        gt = e.ground_truth()
        gt["wallets"] = [_bech32_cosmetic(w) for w in gt["wallets"]]
        ground_truth.append(gt)

    tx_path = os.path.join(OUTPUT_DIR, "bitcoin_transactions.csv")
    with open(tx_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["txid", "wallet", "role", "amount",
                                                "timestamp", "fee", "script_type"])
        writer.writeheader()
        writer.writerows(tx_rows)

    relay_path = os.path.join(OUTPUT_DIR, "relay_events.csv")
    with open(relay_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["txid", "timestamp", "src_ip", "dst_ip",
                                                "src_port", "dst_port"])
        writer.writeheader()
        writer.writerows(relay_rows)

    gt_path = os.path.join(OUTPUT_DIR, "ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Entities generated: {len(all_entities)}")
    print(f"Transaction rows:   {len(tx_rows)}  -> {tx_path}")
    print(f"Relay rows:         {len(relay_rows)}  -> {relay_path}")
    print(f"Ground truth:       {len(ground_truth)} entities -> {gt_path}")
    illicit_count = sum(1 for g in ground_truth if g["is_illicit"])
    print(f"Illicit entities:   {illicit_count} / {len(all_entities)} "
          f"({100*illicit_count/len(all_entities):.1f}%)")


if __name__ == "__main__":
    generate_dataset()

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
    # tor_like_ip_pool is intentionally NOT built here. This dict is a
    # module-level constant, evaluated once at import time -- BEFORE
    # random.seed() ever runs inside generate_dataset(). Building the pool
    # here with random.randint() consumed unseeded (os-random) state on
    # every fresh `python3 generator.py` process, so the pool's actual IP
    # values differed run-to-run even with a fixed seed. Transaction
    # structure was unaffected (doesn't touch this pool's contents), which
    # is why bitcoin_transactions.csv/ground_truth.json hashed identically
    # while relay_events.csv (src_ip values, drawn via seeded random.choice
    # over this pool) did not. See _build_tor_like_ip_pool(), called from
    # generate_dataset() AFTER seeding.
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


def _build_tor_like_ip_pool():
    """Must only be called AFTER random.seed() has run for this process."""
    return [f"185.220.10{n}.{random.randint(1,254)}" for n in range(1, 6)]

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
    config = dict(config or DEFAULT_CONFIG)  # copy — we're about to mutate a key
    random.seed(config.get("seed", 42))
    if "tor_like_ip_pool" not in config or config["tor_like_ip_pool"] is None:
        config["tor_like_ip_pool"] = _build_tor_like_ip_pool()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: every archetype EXCEPT the mixer generates independently and
    # builds up its own wallet history first.
    all_entities = []
    entity_id = 0
    for archetype_name, count in config["archetype_counts"].items():
        if archetype_name == "mixer_coinjoin":
            continue
        cls = ARCHETYPES[archetype_name]
        for _ in range(count):
            entity = cls(entity_id=f"{entity_id:05d}", config=config)
            entity.generate()
            all_entities.append(entity)
            entity_id += 1

    # Phase 2: build a pool of real wallets a mixer could plausibly draw from —
    # legit individuals/businesses seeking privacy, plus darknet vendors laundering
    # proceeds. Deliberately excludes peeling-chain/ransomware wallets: those
    # archetypes already have their own obfuscation technique and mixing them in
    # would blur what each pattern detector is independently supposed to catch.
    pool_types = {"legit_individual", "legit_business", "darknet_vendor"}
    participant_pool = [w for e in all_entities if e.entity_type in pool_types for w in e.wallets]

    mixer_count = config["archetype_counts"].get("mixer_coinjoin", 0)
    cls = ARCHETYPES["mixer_coinjoin"]
    for _ in range(mixer_count):
        entity = cls(entity_id=f"{entity_id:05d}", config=config)
        entity.generate(participant_pool=participant_pool)
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

    # CoinJoin txids, bech32-wrapped, exported separately — this is Tier-2
    # PATTERN DETECTOR ground truth (is this txid a real mix?), not Tier-1
    # entity-clustering ground truth (participants are borrowed real wallets
    # from other entities, not owned by the mixer).
    coinjoin_txids = set()
    for e in all_entities:
        coinjoin_txids.update(getattr(e, "coinjoin_txids", []))
    coinjoin_path = os.path.join(OUTPUT_DIR, "coinjoin_ground_truth.json")
    with open(coinjoin_path, "w") as f:
        json.dump(sorted(coinjoin_txids), f, indent=2)

    print(f"Entities generated: {len(all_entities)}")
    print(f"Transaction rows:   {len(tx_rows)}  -> {tx_path}")
    print(f"Relay rows:         {len(relay_rows)}  -> {relay_path}")
    print(f"Ground truth:       {len(ground_truth)} entities -> {gt_path}")
    illicit_count = sum(1 for g in ground_truth if g["is_illicit"])
    print(f"Illicit entities:   {illicit_count} / {len(all_entities)} "
          f"({100*illicit_count/len(all_entities):.1f}%)")


if __name__ == "__main__":
    generate_dataset()

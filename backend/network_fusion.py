"""
TRACE-X — network_fusion.py (Network-Identity Fusion)
Correlates blockchain-layer clusters/chains with network-layer relay data
(relay_events.csv). Two concrete capabilities:

  1. Peeling-chain infra fingerprinting — for each Tier-2 flagged chain,
     measure how many distinct broadcast IPs were used across its hops.
     Sloppy launderers reuse one IP (diversity ~1); careful launderers
     rotate infra every hop (diversity ~hop_count). This is the direct,
     measurable version of the PS's "correlates network-layer IP/port/timing
     with blockchain-layer wallet/TXID/amount data" framing.

  2. IP-sharing wallet clusters — wallets that broadcast from the same
     source IP across otherwise-unrelated transactions. This is specifically
     aimed at entities Tier-1 structurally cannot resolve (e.g.
     ransomware_collector: single-input/single-output transactions give
     zero common-input or change-address linking opportunity — confirmed
     0/8 in Tier-1 evaluation). If the collector's wallets share a stable
     IP, network fusion recovers a link Tier-1 cannot.
"""

import csv
import json
from collections import defaultdict

from clustering import load_transactions
from pattern_detection import detect_peeling_chains


def load_relay_map(relay_csv_path):
    """txid -> src_ip. (Current schema: one relay row per txid — no
    multi-hop gossip fan-out simulated yet, so src_ip IS the origin, no
    min-timestamp trick needed.)"""
    relay_map = {}
    with open(relay_csv_path) as f:
        for row in csv.DictReader(f):
            relay_map[row["txid"]] = row["src_ip"]
    return relay_map


def build_wallet_ip_map(tx_map, relay_map):
    """wallet -> set of src_ips observed broadcasting a tx where this wallet
    was an INPUT (i.e., the wallet's own node/software did the broadcast —
    output-only appearances don't tell you anything about the recipient's
    infra)."""
    wallet_ips = defaultdict(set)
    for txid, data in tx_map.items():
        ip = relay_map.get(txid)
        if not ip:
            continue
        for wallet, amount, ts in data["inputs"]:
            wallet_ips[wallet].add(ip)
    return wallet_ips


def build_receiving_wallet_ip_map(tx_map, relay_map):
    """wallet -> set of src_ips observed on transactions where this wallet
    was an OUTPUT (recipient). A wallet's OWN broadcasts (input-side) tell
    you about the wallet's own infra; a wallet's RECEIVING-side IPs tell you
    about the SENDERS' infra. For a collector wallet that receives from
    many otherwise-unrelated victims, all sharing one recurring sender IP is
    itself a strong signal (a single automated payout/monitoring script
    broadcasting on behalf of many distinct victim wallets) — a pattern
    input-side fingerprinting is structurally blind to, since the collector
    wallet may only ever appear as an INPUT once (its single sweep-out)."""
    wallet_ips = defaultdict(set)
    for txid, data in tx_map.items():
        ip = relay_map.get(txid)
        if not ip:
            continue
        for wallet, amount, ts in data["outputs"]:
            wallet_ips[wallet].add(ip)
    return wallet_ips


def peeling_chain_ip_diversity(flagged_chains, relay_map):
    """For each flagged peeling chain, look up the src_ip of every hop's
    txid and report how many distinct IPs appear. Attaches a
    'sloppy_or_careful' guess: <=2 distinct IPs -> sloppy-like, otherwise
    careful-like (independent heuristic threshold, not read from config)."""
    results = []
    for chain in flagged_chains:
        ips = [relay_map.get(txid) for txid in chain["txids"] if relay_map.get(txid)]
        distinct = len(set(ips))
        guess = "sloppy_like" if distinct <= 2 else "careful_like"
        results.append({
            "chain_wallets": chain["chain_wallets"],
            "hop_count": chain["hop_count"],
            "distinct_ips_used": distinct,
            "ip_diversity_ratio": round(distinct / chain["hop_count"], 4),
            "infra_guess": guess,
        })
    return results


def evaluate_ip_diversity_vs_ground_truth(diversity_results, chains_raw, ground_truth_path, overlap_threshold=0.8):
    """Cross-references each chain's infra_guess against its TRUE archetype
    (peeling_chain_sloppy vs peeling_chain_careful) via wallet-set overlap —
    same matching approach as pattern_detection's own evaluator."""
    gt = json.load(open(ground_truth_path))
    true_peeling = [g for g in gt if g["entity_type"] in ("peeling_chain_sloppy", "peeling_chain_careful")]

    def overlap_frac(a, b):
        a, b = set(a), set(b)
        return len(a & b) / len(a | b) if a and b else 0.0

    correct, total_matched = 0, 0
    for dr in diversity_results:
        best_entity, best_overlap = None, 0.0
        for g in true_peeling:
            ov = overlap_frac(dr["chain_wallets"], g["wallets"])
            if ov > best_overlap:
                best_overlap, best_entity = ov, g
        if best_overlap >= overlap_threshold:
            total_matched += 1
            true_label = "sloppy_like" if best_entity["entity_type"] == "peeling_chain_sloppy" else "careful_like"
            if true_label == dr["infra_guess"]:
                correct += 1

    return {
        "chains_matched_to_ground_truth": total_matched,
        "infra_guess_accuracy": round(correct / total_matched, 4) if total_matched else None,
    }


def find_ip_sharing_clusters(wallet_ips, min_shared_wallets=2):
    """ip -> list of wallets that ever broadcast from it. Only IPs shared by
    >= min_shared_wallets are returned — a unique IP per wallet carries no
    linking signal."""
    ip_to_wallets = defaultdict(set)
    for wallet, ips in wallet_ips.items():
        for ip in ips:
            ip_to_wallets[ip].add(wallet)
    return {ip: sorted(wallets) for ip, wallets in ip_to_wallets.items() if len(wallets) >= min_shared_wallets}


def evaluate_ransomware_recovery(tx_map, relay_map, ground_truth_path, min_unrelated_senders=3):
    """
    Real ransomware-collector signal: does a wallet receive multiple
    payments from DISTINCT, otherwise-unrelated sender wallets that were
    all broadcast from the SAME recurring src_ip? This is the
    receiving-side fingerprint (a single automated collection endpoint),
    independent of whether the collector wallet itself ever appears as an
    input elsewhere.
    """
    gt = json.load(open(ground_truth_path))
    ransomware = [g for g in gt if g["entity_type"] == "ransomware_collector"]

    # collector_wallet -> {sender_wallet -> src_ip} across all inbound txs
    inbound_by_recipient = defaultdict(dict)
    for txid, data in tx_map.items():
        ip = relay_map.get(txid)
        if not ip:
            continue
        input_wallets = [w for w, a, t in data["inputs"]]
        if len(input_wallets) != 1:
            continue
        sender = input_wallets[0]
        for wallet, amount, ts in data["outputs"]:
            inbound_by_recipient[wallet][sender] = ip

    recovered = 0
    for g in ransomware:
        # the collector wallet is whichever of this entity's wallets has
        # multiple distinct inbound senders (the "next_hop" sweep-target
        # wallet has none)
        collector_candidates = [w for w in g["wallets"] if len(inbound_by_recipient.get(w, {})) >= min_unrelated_senders]
        if not collector_candidates:
            continue
        for collector in collector_candidates:
            sender_ips = list(inbound_by_recipient[collector].values())
            most_common_ip_count = max((sender_ips.count(ip) for ip in set(sender_ips)), default=0)
            if most_common_ip_count >= min_unrelated_senders:
                recovered += 1
                break

    return {
        "ransomware_entities_total": len(ransomware),
        "ransomware_entities_recovered_via_receiving_side_ip": recovered,
        "recovery_rate": round(recovered / len(ransomware), 4) if ransomware else None,
    }


if __name__ == "__main__":
    tx_map = load_transactions("dataset/output/bitcoin_transactions.csv")
    relay_map = load_relay_map("dataset/output/relay_events.csv")
    wallet_ips = build_wallet_ip_map(tx_map, relay_map)

    flagged_chains, _ = detect_peeling_chains("dataset/output/bitcoin_transactions.csv")
    diversity_results = peeling_chain_ip_diversity(flagged_chains, relay_map)

    print("Peeling-chain infra fingerprint (sample):")
    for d in diversity_results[:6]:
        print(f"  hops={d['hop_count']}  distinct_ips={d['distinct_ips_used']}  "
              f"diversity_ratio={d['ip_diversity_ratio']}  guess={d['infra_guess']}")

    diversity_eval = evaluate_ip_diversity_vs_ground_truth(diversity_results, flagged_chains, "dataset/output/ground_truth.json")
    print(f"\nInfra-guess accuracy vs true sloppy/careful label:")
    print(json.dumps(diversity_eval, indent=2))

    ip_clusters = find_ip_sharing_clusters(wallet_ips)
    print(f"\nIP-sharing clusters found (>=2 wallets, input-side): {len(ip_clusters)}")

    ransomware_eval = evaluate_ransomware_recovery(tx_map, relay_map, "dataset/output/ground_truth.json")
    print(f"\nRansomware-collector recovery via RECEIVING-side IP fusion (Tier-1 was 0/8 linking opportunity):")
    print(json.dumps(ransomware_eval, indent=2))

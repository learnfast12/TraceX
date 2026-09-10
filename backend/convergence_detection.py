"""
TRACE-X — convergence_detection.py (Tier 2)
Darknet-vendor sweep detector ("Convergence Analysis" per solution doc
Section 5, PS focus area: Anomaly Detection).

Peeling-chain detection (pattern_detection.py) catches one-to-one hop
chains. It structurally cannot catch a many-to-one CONSOLIDATION: a
darknet vendor collects many small, economically-unrelated buyer payments
across a pool of disposable receiving wallets, then periodically sweeps
that pool into a single vault wallet in one multi-input transaction.
Each receiving wallet, taken alone, looks like an ordinary one-shot
recipient — nothing about a single wallet's history is suspicious. The
signal only appears when you look ACROSS the swept wallets at once:
their prior deposits, despite coming from unrelated buyer wallets, were
broadcast from the same small pool of IPs — the vendor's own
infrastructure receiving payment, not the buyers'.

Independent thresholds (not copied from the generator's own pending-queue
config) so evaluation numbers reflect genuine detection capability.
"""

import json
from collections import defaultdict

from clustering import load_transactions
from network_fusion import load_relay_map

MIN_SWEEP_INPUTS = 5          # fewer inputs than this isn't a strong enough consolidation signal
MAX_DISTINCT_DEPOSIT_IPS = 5  # swept wallets' funding txs must trace back to a small IP pool
MIN_IP_REUSE_RATIO = 2.0      # avg deposits per distinct IP among the funding txs — reuse, not coincidence


def build_incoming_index(tx_map):
    """wallet -> list of (txid, timestamp) for every tx where wallet received funds."""
    incoming = defaultdict(list)
    for txid, data in tx_map.items():
        for w, amount, ts in data["outputs"]:
            incoming[w].append((txid, ts))
    return incoming


def find_sweep_candidates(tx_map, relay_map, incoming_index):
    """
    Multi-input, single-output transactions where the input wallets'
    PRIOR deposits (before this tx's own timestamp) trace back to a
    small, reused set of relay IPs.
    """
    candidates = []

    for txid, data in tx_map.items():
        input_wallets = [w for w, amt, ts in data["inputs"]]
        if len(input_wallets) < MIN_SWEEP_INPUTS:
            continue
        if len(data["outputs"]) != 1:
            continue  # a sweep consolidates to one vault wallet

        vault_wallet, total_amount, sweep_ts = data["outputs"][0]

        deposit_ips = []
        for w in input_wallets:
            for dep_txid, dep_ts in incoming_index.get(w, []):
                if dep_ts >= sweep_ts:
                    continue  # only deposits that happened BEFORE this sweep
                ip = relay_map.get(dep_txid)
                if ip:
                    deposit_ips.append(ip)

        if not deposit_ips:
            continue

        distinct_ips = set(deposit_ips)
        reuse_ratio = len(deposit_ips) / len(distinct_ips)

        if len(distinct_ips) > MAX_DISTINCT_DEPOSIT_IPS:
            continue
        if reuse_ratio < MIN_IP_REUSE_RATIO:
            continue

        candidates.append({
            "txid": txid,
            "vault_wallet": vault_wallet,
            "input_wallets": input_wallets,
            "wallets": input_wallets + [vault_wallet],
            "input_count": len(input_wallets),
            "distinct_deposit_ips": len(distinct_ips),
            "ip_reuse_ratio": round(reuse_ratio, 4),
            "total_amount": total_amount,
        })

    return candidates


def score_sweep(candidate):
    """
    Confidence in [0, 1] from two independent signals:
      - input_count: more consolidated wallets is stronger evidence
      - ip_concentration: fewer distinct IPs relative to input count,
        plus higher reuse, points to one operator's infrastructure
        rather than coincidence
    """
    input_count_score = min(candidate["input_count"] / 15.0, 1.0)

    concentration = 1.0 - (candidate["distinct_deposit_ips"] / max(candidate["input_count"], 1))
    reuse_score = min(candidate["ip_reuse_ratio"] / 5.0, 1.0)
    ip_score = round(0.5 * concentration + 0.5 * reuse_score, 4)

    return round(0.5 * input_count_score + 0.5 * ip_score, 4)


def detect_darknet_sweeps(tx_csv_path, relay_map):
    tx_map = load_transactions(tx_csv_path)
    incoming_index = build_incoming_index(tx_map)

    candidates = find_sweep_candidates(tx_map, relay_map, incoming_index)
    flagged = []
    for c in candidates:
        confidence = score_sweep(c)
        flagged.append({**c, "confidence": confidence})

    flagged.sort(key=lambda c: c["confidence"], reverse=True)
    return flagged


def evaluate_against_ground_truth(flagged_sweeps, ground_truth_path, overlap_threshold=0.5):
    """
    Precision: of the flagged sweeps, how many substantially overlap
    (>= overlap_threshold of wallets) with a true darknet_vendor entity?
    Recall: of the true darknet_vendor entities, how many are recovered
    by AT LEAST ONE flagged sweep? (A vendor typically sweeps multiple
    times — recall only needs one hit per entity, not every sweep caught.)
    """
    gt = json.load(open(ground_truth_path))
    true_vendors = [g for g in gt if g["entity_type"] == "darknet_vendor"]

    def overlap_frac(a, b):
        a, b = set(a), set(b)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    tp_sweeps = 0
    matched_entities = set()
    for sweep in flagged_sweeps:
        best_overlap = 0.0
        best_entity = None
        for g in true_vendors:
            ov = overlap_frac(sweep["wallets"], g["wallets"])
            if ov > best_overlap:
                best_overlap = ov
                best_entity = g["entity_id"]
        if best_overlap >= overlap_threshold:
            tp_sweeps += 1
            matched_entities.add(best_entity)

    precision = tp_sweeps / len(flagged_sweeps) if flagged_sweeps else None
    recall = len(matched_entities) / len(true_vendors) if true_vendors else None

    return {
        "true_darknet_vendor_entities": len(true_vendors),
        "flagged_sweeps": len(flagged_sweeps),
        "sweeps_matching_a_true_entity": tp_sweeps,
        "true_entities_recovered": len(matched_entities),
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
    }


if __name__ == "__main__":
    relay_map = load_relay_map("dataset/output/relay_events.csv")
    flagged = detect_darknet_sweeps("dataset/output/bitcoin_transactions.csv", relay_map)

    print(f"Candidate sweeps flagged: {len(flagged)}")
    print(f"\nTop 5 by confidence:")
    for s in flagged[:5]:
        print(f"  inputs={s['input_count']}  distinct_ips={s['distinct_deposit_ips']}  "
              f"reuse_ratio={s['ip_reuse_ratio']}  confidence={s['confidence']}  "
              f"vault={s['vault_wallet'][:14]}...")

    metrics = evaluate_against_ground_truth(flagged, "dataset/output/ground_truth.json")
    print(f"\nEvaluation against ground truth:")
    print(json.dumps(metrics, indent=2))

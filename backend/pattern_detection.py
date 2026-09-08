"""
TRACE-X — pattern_detection.py (Tier 2)
Peeling-chain traversal detector.

Tier-1 clustering (clustering.py) already links peeling-chain hops together
via the change-address heuristic (a fresh, later-respent remainder wallet
looks structurally identical to legit change). That tells you WHICH wallets
belong together — it says nothing about WHETHER the pattern is a peeling
chain. This module adds that layer: walk the hop graph independently, using
its own skew/length thresholds (never the generator's own config values —
that would be evaluating the detector against its own answer key), and
flag chains that match the peeling shape.

Peeling signature: a 2-output transaction where one output is a small
"peel" (cash-out/payment) and the other is a large, FRESH, later-respent
remainder — repeated over several hops. Distinguishing signal vs. ordinary
legit change: peeling splits are heavily skewed (small peel << large
remainder); legit payment+change splits are much closer to balanced.
"""

import json
import statistics
from collections import defaultdict

from clustering import (
    load_transactions, compute_first_seen, compute_ever_spent_from,
    is_likely_coinjoin,
)

# Independent detector thresholds — NOT copied from the generator's config,
# so evaluation numbers reflect genuine detection capability rather than
# circular knowledge of how the data was made.
SKEW_RATIO_THRESHOLD = 0.20   # smaller_output / larger_output must be below this to count as "peel-shaped"
MIN_CHAIN_HOPS = 3            # minimum hops before we're willing to call it a peeling chain
MAX_HOP_INTERVAL_HOURS = 6.0  # hops slower than this are still counted, but penalized in confidence


def find_peel_hops(tx_map, first_seen, ever_spent_from):
    """
    Returns hop_from[wallet] = {txid, timestamp, next_wallet, peel_sink,
    peeled_amount, remainder_amount, skew_ratio} for every transaction that
    matches the peel shape: 1 input wallet, exactly 2 outputs, exactly one
    output qualifies as a change-address candidate (fresh + later respent),
    and the split is skewed past SKEW_RATIO_THRESHOLD.
    """
    hop_from = {}

    for txid, data in tx_map.items():
        if is_likely_coinjoin(data):
            continue

        input_wallets = [w for w, amt, ts in data["inputs"]]
        if len(input_wallets) != 1:
            continue  # peeling hops are single-input by construction

        outputs = data["outputs"]
        if len(outputs) != 2:
            continue

        candidates = []
        for wallet, amount, ts in outputs:
            is_fresh = first_seen.get(wallet) == ts
            is_respent = wallet in ever_spent_from
            if is_fresh and is_respent:
                candidates.append((wallet, amount))

        if len(candidates) != 1:
            continue

        next_wallet, remainder_amount = candidates[0]
        other = [(w, a) for w, a, ts in outputs if w != next_wallet]
        if len(other) != 1:
            continue
        peel_sink, peeled_amount = other[0]

        lo, hi = sorted([peeled_amount, remainder_amount])
        if hi == 0:
            continue
        skew_ratio = lo / hi
        if skew_ratio >= SKEW_RATIO_THRESHOLD:
            continue  # too balanced to be a peel — looks like ordinary change

        ts = outputs[0][2]  # both outputs share the tx timestamp in this schema
        hop_from[input_wallets[0]] = {
            "txid": txid,
            "timestamp": ts,
            "next_wallet": next_wallet,
            "peel_sink": peel_sink,
            "peeled_amount": peeled_amount,
            "remainder_amount": remainder_amount,
            "skew_ratio": round(skew_ratio, 4),
        }

    return hop_from


def walk_chains(hop_from):
    """
    Chains together consecutive hops: wallet A -> next_wallet B (via one
    hop) -> next_wallet C (via another hop) -> ... Chain roots are wallets
    that START a hop but are never themselves a next_wallet of another hop
    (i.e., nothing feeds into them from an earlier peel).

    Also tracks peel_sink_wallets separately from the remainder-chain
    wallets. A peel_sink is the cash-out destination of a single peel —
    by construction it never respends within the chain (that's what makes
    it the "peeled off" amount rather than the passed-along remainder), so
    it can never become anyone's next_wallet and is structurally invisible
    to the remainder-only `wallets` list. Ground truth counts these as
    entity members; omitting them silently under-recalls every chain by
    its hop count. They carry a different investigative meaning (cash-out
    point, not a laundering hop) so they're reported as a distinct field
    rather than merged into `wallets`.
    """
    is_next_wallet = set(h["next_wallet"] for h in hop_from.values())
    roots = [w for w in hop_from if w not in is_next_wallet]

    chains = []
    for root in roots:
        chain_wallets = [root]
        chain_hops = []
        peel_sink_wallets = []
        current = root
        seen = {root}
        while current in hop_from:
            hop = hop_from[current]
            chain_hops.append(hop)
            peel_sink_wallets.append(hop["peel_sink"])
            nxt = hop["next_wallet"]
            if nxt in seen:
                break  # guard against any accidental cycle
            chain_wallets.append(nxt)
            seen.add(nxt)
            current = nxt
        chains.append({
            "wallets": chain_wallets,
            "hops": chain_hops,
            "peel_sink_wallets": peel_sink_wallets,
        })
    return chains


def score_chain(chain):
    """
    Confidence score in [0, 1] from three independent signals:
      - length: longer chains are stronger evidence (saturates past ~8 hops)
      - skew consistency: real peeling chains keep a fairly stable peel
        fraction hop-to-hop; std-dev of skew_ratio should be low
      - timing regularity: peeling hops tend to be fast and somewhat
        regular; very slow or wildly irregular gaps score lower
    """
    hops = chain["hops"]
    n = len(hops)
    if n == 0:
        return 0.0

    length_score = min(n / 8.0, 1.0)

    skews = [h["skew_ratio"] for h in hops]
    skew_std = statistics.pstdev(skews) if len(skews) > 1 else 0.0
    skew_consistency_score = max(0.0, 1.0 - (skew_std / SKEW_RATIO_THRESHOLD))

    timestamps = [h["timestamp"] for h in hops]
    try:
        from datetime import datetime
        parsed = [datetime.fromisoformat(t) for t in timestamps]
        intervals_hours = [
            (parsed[i + 1] - parsed[i]).total_seconds() / 3600
            for i in range(len(parsed) - 1)
        ] if len(parsed) > 1 else []
        if intervals_hours:
            over_limit_frac = sum(1 for iv in intervals_hours if iv > MAX_HOP_INTERVAL_HOURS) / len(intervals_hours)
            timing_score = 1.0 - over_limit_frac
        else:
            timing_score = 0.5  # single-hop chain, not enough data — neutral
    except Exception:
        timing_score = 0.5

    return round(0.45 * length_score + 0.30 * skew_consistency_score + 0.25 * timing_score, 4)


def detect_peeling_chains(tx_csv_path):
    tx_map = load_transactions(tx_csv_path)
    excluded = set(txid for txid, data in tx_map.items() if is_likely_coinjoin(data))
    first_seen = compute_first_seen(tx_map, excluded_txids=excluded)
    ever_spent_from = compute_ever_spent_from(tx_map, excluded_txids=excluded)

    hop_from = find_peel_hops(tx_map, first_seen, ever_spent_from)
    all_chains = walk_chains(hop_from)

    flagged = []
    for chain in all_chains:
        if len(chain["hops"]) < MIN_CHAIN_HOPS:
            continue
        confidence = score_chain(chain)
        flagged.append({
            "chain_wallets": chain["wallets"],
            "peel_sink_wallets": chain["peel_sink_wallets"],
            "hop_count": len(chain["hops"]),
            "avg_skew_ratio": round(statistics.mean(h["skew_ratio"] for h in chain["hops"]), 4),
            "txids": [h["txid"] for h in chain["hops"]],
            "confidence": confidence,
        })

    flagged.sort(key=lambda c: c["confidence"], reverse=True)
    return flagged, all_chains


def evaluate_against_ground_truth(flagged_chains, ground_truth_path, overlap_threshold=0.8):
    """
    Precision: of the chains we flagged, how many overlap substantially
    (>= overlap_threshold of wallets) with a TRUE peeling-chain entity?
    Recall: of the true peeling-chain entities, how many were substantially
    recovered by at least one flagged chain?
    """
    gt = json.load(open(ground_truth_path))
    true_peeling = [g for g in gt if g["entity_type"] in ("peeling_chain_sloppy", "peeling_chain_careful")]

    def overlap_frac(a, b):
        a, b = set(a), set(b)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    tp_chains = 0
    matched_entities = set()
    for chain in flagged_chains:
        best_overlap = 0.0
        best_entity = None
        for g in true_peeling:
            ov = overlap_frac(chain["chain_wallets"], g["wallets"])
            if ov > best_overlap:
                best_overlap = ov
                best_entity = g["entity_id"]
        if best_overlap >= overlap_threshold:
            tp_chains += 1
            matched_entities.add(best_entity)

    precision = tp_chains / len(flagged_chains) if flagged_chains else None
    recall = len(matched_entities) / len(true_peeling) if true_peeling else None

    return {
        "true_peeling_entities": len(true_peeling),
        "flagged_chains": len(flagged_chains),
        "chains_matching_a_true_entity": tp_chains,
        "true_entities_recovered": len(matched_entities),
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
    }


if __name__ == "__main__":
    flagged, all_chains = detect_peeling_chains("dataset/output/bitcoin_transactions.csv")

    print(f"Total hop-chains found (any length): {len(all_chains)}")
    print(f"Chains flagged as peeling (>= {MIN_CHAIN_HOPS} hops): {len(flagged)}")
    print(f"\nTop 5 flagged chains by confidence:")
    for c in flagged[:5]:
        print(f"  hops={c['hop_count']}  avg_skew={c['avg_skew_ratio']}  confidence={c['confidence']}  "
              f"wallets={c['chain_wallets'][0][:14]}...->...{c['chain_wallets'][-1][:14]}...")

    metrics = evaluate_against_ground_truth(flagged, "dataset/output/ground_truth.json")
    print(f"\nEvaluation against ground truth:")
    print(json.dumps(metrics, indent=2))

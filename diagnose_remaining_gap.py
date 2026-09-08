"""
TRACE-X — diagnose_remaining_gap.py
One-shot root-cause diagnostic for the post-sweep-detector recall gap
(39 illicit wallets, 0.9194 -> ? ). Two independent failure surfaces:

  A) peeling_chain_sloppy (15) + peeling_chain_careful (12) = 27 wallets
     -> classifies WHERE in the pipeline they're lost:
        (1) never even form a hop  (find_peel_hops candidate-selection miss)
        (2) form a hop but chain never reaches MIN_CHAIN_HOPS (length miss)
        (3) form a >=MIN_CHAIN_HOPS chain but this wallet isn't IN it
            (e.g. it's the final un-respent remainder, which by definition
            can never be a `next_wallet` of another hop — structural, not a bug)

  B) ransomware_collector (8), tx_involvement=1
     -> classifies WHERE the IP-fingerprint seed path fails:
        (1) never relayed at all (no entry in relay_map)
        (2) relayed but sender count < 3 (threshold cutoff)
        (3) relayed, 3+ senders, but most_common_count < 3 (dispersed IPs —
            i.e. the ONE relay observed doesn't repeat because there's only
            one incoming tx, so "IP reuse across senders" is structurally
            unobservable from a single transaction)

Run from repo root: python3 /tmp/diagnose_remaining_gap.py
(or wherever you copy this — adjust sys.path.insert if not at repo root)
"""

import sys
import json
from collections import defaultdict

sys.path.insert(0, "backend")

from clustering import (
    load_transactions, compute_first_seen, compute_ever_spent_from,
    is_likely_coinjoin,
)
from pattern_detection import find_peel_hops, walk_chains, MIN_CHAIN_HOPS
from network_fusion import load_relay_map
from convergence_detection import detect_darknet_sweeps

TX_CSV = "dataset/output/bitcoin_transactions.csv"
RELAY_CSV = "dataset/output/relay_events.csv"
GT_JSON = "dataset/output/ground_truth.json"

MIN_SENDERS_FOR_SEED = 3      # mirrors build_seeds() threshold
MIN_REUSE_COUNT_FOR_SEED = 3  # mirrors build_seeds() threshold


def load_ground_truth():
    gt = json.load(open(GT_JSON))
    wallet_gt = {}
    for entity in gt:
        for w in entity.get("wallets", []):
            wallet_gt[w] = entity
    return gt, wallet_gt


def section(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------------
# A) Peeling-chain wallets: where in the pipeline are they lost?
# ---------------------------------------------------------------------

def diagnose_peeling_gap(tx_map, wallet_gt, all_illicit_missed):
    section("A) PEELING-CHAIN WALLETS — pipeline loss classification")

    excluded = set(txid for txid, d in tx_map.items() if is_likely_coinjoin(d))
    first_seen = compute_first_seen(tx_map, excluded_txids=excluded)
    ever_spent_from = compute_ever_spent_from(tx_map, excluded_txids=excluded)
    hop_from = find_peel_hops(tx_map, first_seen, ever_spent_from)
    all_chains = walk_chains(hop_from)  # unfiltered by MIN_CHAIN_HOPS

    # index: which chain (if any) does each wallet appear in, and at what length
    wallet_to_chain_len = {}
    for chain in all_chains:
        for w in chain["wallets"]:
            # a wallet could theoretically appear in >1 broken chain segment;
            # keep the longest for a fair read
            prev = wallet_to_chain_len.get(w, -1)
            wallet_to_chain_len[w] = max(prev, len(chain["hops"]))

    is_hop_source = set(hop_from.keys())
    is_hop_target = set(h["next_wallet"] for h in hop_from.values())

    peeling_missed = {
        w: rec for w, rec in all_illicit_missed.items()
        if rec.get("entity_type") in ("peeling_chain_sloppy", "peeling_chain_careful")
    }

    buckets = defaultdict(list)
    for w in peeling_missed:
        if w not in is_hop_source and w not in is_hop_target:
            buckets["1_never_forms_a_hop"].append(w)
        elif w in wallet_to_chain_len and wallet_to_chain_len[w] < MIN_CHAIN_HOPS:
            buckets["2_hop_exists_but_chain_too_short"].append(w)
        elif w in wallet_to_chain_len and wallet_to_chain_len[w] >= MIN_CHAIN_HOPS:
            buckets["3_in_qualifying_chain_but_excluded"].append(w)
        else:
            buckets["4_unclassified"].append(w)

    for key in sorted(buckets):
        wallets = buckets[key]
        print(f"\n  [{key}]  {len(wallets)} wallets")
        for w in wallets[:5]:
            rec = peeling_missed[w]
            chain_len = wallet_to_chain_len.get(w, "n/a")
            role = "source" if w in is_hop_source else ("target-only" if w in is_hop_target else "isolated")
            print(f"    {w[:20]}...  type={rec['entity_type']}  role={role}  best_chain_hops={chain_len}")

    # For bucket 1 specifically, show WHY find_peel_hops rejected the tx
    # (multi-input? not exactly 2 outputs? no fresh+respent candidate? skew too balanced?)
    if buckets["1_never_forms_a_hop"]:
        print("\n  --- Root-cause detail for '1_never_forms_a_hop' (first 5) ---")
        for w in buckets["1_never_forms_a_hop"][:5]:
            explain_never_forms_hop(w, tx_map, first_seen, ever_spent_from, excluded)

    return buckets


def explain_never_forms_hop(wallet, tx_map, first_seen, ever_spent_from, excluded):
    """Find every tx where `wallet` is the sole input and explain why
    find_peel_hops's candidate filters rejected it."""
    hits = 0
    for txid, data in tx_map.items():
        if txid in excluded:
            continue
        input_wallets = [w for w, amt, ts in data["inputs"]]
        if input_wallets != [wallet]:
            continue
        hits += 1
        outputs = data["outputs"]
        reasons = []
        if len(outputs) != 2:
            reasons.append(f"outputs={len(outputs)} (need exactly 2)")
        else:
            candidates = []
            for w2, amount, ts in outputs:
                is_fresh = first_seen.get(w2) == ts
                is_respent = w2 in ever_spent_from
                candidates.append((w2, is_fresh, is_respent))
            n_qualifying = sum(1 for _, f, r in candidates if f and r)
            if n_qualifying != 1:
                reasons.append(f"{n_qualifying} outputs qualify as fresh+respent (need exactly 1)")
                for w2, f, r in candidates:
                    reasons.append(f"    -> {w2[:16]}...  fresh={f}  ever_respent={r}")
            else:
                lo, hi = sorted(a for _, a, ts in outputs)
                skew = lo / hi if hi else None
                reasons.append(f"skew_ratio={skew} (threshold check happens after this point)")
        print(f"    wallet={wallet[:16]}...  txid={txid[:16]}...  " + " | ".join(reasons))
    if hits == 0:
        print(f"    wallet={wallet[:16]}...  is NEVER the sole input of any non-CoinJoin tx "
              f"(multi-input spend, or only ever a recipient, or CoinJoin-excluded)")


# ---------------------------------------------------------------------
# B) Ransomware-collector wallets: where does the IP-seed path fail?
# ---------------------------------------------------------------------

def diagnose_ransomware_gap(tx_map, relay_map, wallet_gt, all_illicit_missed):
    section("B) RANSOMWARE-COLLECTOR WALLETS — IP-seed path classification")

    inbound_by_recipient = defaultdict(dict)
    for txid, data in tx_map.items():
        ip = relay_map.get(txid)
        input_wallets = [w for w, a, t in data["inputs"]]
        if len(input_wallets) != 1:
            continue
        sender = input_wallets[0]
        for wallet, amount, ts in data["outputs"]:
            if ip:
                inbound_by_recipient[wallet][sender] = ip

    ransom_missed = {
        w: rec for w, rec in all_illicit_missed.items()
        if rec.get("entity_type") == "ransomware_collector"
    }

    buckets = defaultdict(list)
    for w in ransom_missed:
        senders = inbound_by_recipient.get(w, {})
        if not senders:
            buckets["1_no_relayed_incoming_tx"].append((w, senders))
        elif len(senders) < MIN_SENDERS_FOR_SEED:
            buckets["2_below_min_senders_threshold"].append((w, senders))
        else:
            ips = list(senders.values())
            most_common = max(ips.count(ip) for ip in set(ips))
            if most_common < MIN_REUSE_COUNT_FOR_SEED:
                buckets["3_senders_ok_but_ip_dispersed"].append((w, senders))
            else:
                buckets["4_unclassified_should_have_seeded"].append((w, senders))

    for key in sorted(buckets):
        items = buckets[key]
        print(f"\n  [{key}]  {len(items)} wallets")
        for w, senders in items[:8]:
            print(f"    {w[:20]}...  distinct_senders={len(senders)}  "
                  f"sample_ips={list(senders.values())[:3]}")

    return buckets


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    tx_map = load_transactions(TX_CSV)
    relay_map = load_relay_map(RELAY_CSV)
    gt, wallet_gt = load_ground_truth()

    # Recompute current-state seeds INCLUDING the sweep detector, so this
    # diagnostic reflects the 0.9194-recall baseline, not the pre-sweep one.
    from pattern_detection import detect_peeling_chains
    from risk_scoring import build_seeds

    flagged_chains, _ = detect_peeling_chains(TX_CSV)
    flagged_sweeps = detect_darknet_sweeps(TX_CSV, relay_map)
    seeds = build_seeds(tx_map, relay_map, flagged_chains, GT_JSON, flagged_sweeps=flagged_sweeps)

    illicit_wallets = {w: rec for w, rec in wallet_gt.items() if rec.get("is_illicit")}
    still_missed = {w: rec for w, rec in illicit_wallets.items() if seeds.get(w, 0.0) == 0.0}

    section("BASELINE")
    print(f"  Total illicit wallets: {len(illicit_wallets)}")
    print(f"  Currently seeded (post-sweep-detector): {len(illicit_wallets) - len(still_missed)}  "
          f"(recall {(len(illicit_wallets) - len(still_missed)) / len(illicit_wallets):.4f})")
    print(f"  Still missed: {len(still_missed)}")

    by_type = defaultdict(int)
    for rec in still_missed.values():
        by_type[rec.get("entity_type", "unknown")] += 1
    print("\n  By entity_type:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t}: {n}")

    peel_buckets = diagnose_peeling_gap(tx_map, wallet_gt, still_missed)
    ransom_buckets = diagnose_ransomware_gap(tx_map, relay_map, wallet_gt, still_missed)

    section("SUMMARY — recommended next action per bucket")
    print(f"""
  Peeling (A):
    1_never_forms_a_hop            -> {len(peel_buckets.get('1_never_forms_a_hop', []))}
      If nonzero: real detector miss. Check the printed rejection reasons above —
      likely >2 outputs (change + peel + dust) or 0/2 qualifying candidates.
      Fix in find_peel_hops candidate logic, NOT a threshold tweak.

    2_hop_exists_but_chain_too_short -> {len(peel_buckets.get('2_hop_exists_but_chain_too_short', []))}
      If this dominates: these are genuinely short chains (1-2 hops) that the
      generator legitimately produced. Options: (a) lower MIN_CHAIN_HOPS with
      a documented precision/recall tradeoff re-run, (b) add a lower-confidence
      "short-peel" seed tier instead of an all-or-nothing cutoff, seeded at a
      reduced weight (e.g. 0.3-0.4) so PPR can still surface it without
      polluting CRITICAL-tier precision.

    3_in_qualifying_chain_but_excluded -> {len(peel_buckets.get('3_in_qualifying_chain_but_excluded', []))}
      Expected and mostly benign: the final un-respent remainder wallet in a
      chain is a legitimate terminus, not a missed detection — it's simply
      never anyone's `next_wallet`. Confirm via the role= printout above
      (should show role=isolated on the terminal wallet). If nonzero here
      shows role=source/target unexpectedly, that's a real bug in walk_chains.

  Ransomware (B):
    1_no_relayed_incoming_tx        -> {len(ransom_buckets.get('1_no_relayed_incoming_tx', []))}
      Structural: single-tx collector with no relay observation at all.
      No amount of threshold tuning fixes this — needs a second, independent
      signal (e.g. destination-wallet reputation, amount-pattern anomaly,
      or first_seen entropy) since network-fusion has literally nothing to see.

    2_below_min_senders_threshold   -> {len(ransom_buckets.get('2_below_min_senders_threshold', []))}
      Tunable: MIN_SENDERS_FOR_SEED=3 assumes multiple ransom payments before
      a wallet gets flagged. If tx_involvement=1 for all 8, by definition they
      can NEVER clear a 3-sender threshold from a single wallet. This is the
      real bug: build_seeds' ransomware path is structurally blind to a
      collector wallet used exactly once. Needs a single-tx path: e.g. relay
      IP matches a KNOWN-BAD IP/ASN list (ransomware demand addresses, per
      solution doc Section 5.5) rather than requiring in-dataset repetition.

    3_senders_ok_but_ip_dispersed   -> {len(ransom_buckets.get('3_senders_ok_but_ip_dispersed', []))}
      Genuine detector miss on a wallet that DID get enough sender diversity
      but IP reuse fell under MIN_REUSE_COUNT_FOR_SEED — worth checking raw
      IP list before lowering the threshold (risk of precision collapse on
      MEDIUM/CLEAR tiers, which are already at 0.05/0.007 precision).
""")


if __name__ == "__main__":
    main()

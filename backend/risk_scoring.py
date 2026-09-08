"""
TRACE-X — risk_scoring.py
Final wallet-level risk score, combining three independently-validated
signal families into one ranked, explainable output:

  1. Structural evidence   — Tier-1 cluster membership + Tier-2 pattern
                              flags (peeling-chain hop, confidence)
  2. Network-origin evidence — receiving-side IP fingerprint match
                              (ransomware-style single-collector-IP pattern)
  3. Propagated risk        — Personalized PageRank over the wallet
                              value-flow graph, seeded from (1) and (2)'s
                              highest-confidence hits — NOT from ground
                              truth. Ground truth (is_illicit) is used only
                              at the end, to evaluate the final score.

Score = weighted blend of direct evidence + propagated exposure, mapped to
CRITICAL / HIGH / MEDIUM / CLEAR tiers (same philosophy as TraceNetX's
tiering, now driven by real detector output instead of name-string rules).
"""

import json
from collections import defaultdict

from clustering import load_transactions, cluster_entities
from pattern_detection import detect_peeling_chains
from convergence_detection import detect_darknet_sweeps
from network_fusion import load_relay_map, evaluate_ransomware_recovery

DAMPING = 0.85
PPR_ITERATIONS = 60
SEED_RESTART_MASS = 1.0  # total probability mass distributed across seeds each restart


# ---------------------------------------------------------------------
# 1. Wallet value-flow graph
# ---------------------------------------------------------------------

def build_wallet_graph(tx_map):
    """
    Directed wallet->wallet edges, weighted by value flow. For a tx with
    multiple inputs and outputs, value is attributed evenly across input
    wallets (a simplifying assumption — exact per-input attribution is
    genuinely ambiguous in the UTXO model without extra heuristics).
    Returns: out_edges[wallet] = {dest_wallet: weight, ...}
    """
    out_edges = defaultdict(lambda: defaultdict(float))
    for txid, data in tx_map.items():
        inputs = [w for w, a, t in data["inputs"]]
        outputs = data["outputs"]
        if not inputs or not outputs:
            continue
        share = 1.0 / len(inputs)
        for in_wallet in inputs:
            for out_wallet, amount, ts in outputs:
                if out_wallet == in_wallet:
                    continue
                out_edges[in_wallet][out_wallet] += amount * share
    return out_edges


# ---------------------------------------------------------------------
# 2. Seed construction — from OUR OWN detectors, never from ground truth
# ---------------------------------------------------------------------

def build_seeds(tx_map, relay_map, flagged_chains, ground_truth_path_for_wallet_universe, flagged_sweeps=None, enable_ip_crossref=True):
    """
    seeds[wallet] = confidence in [0, 1], used as restart-distribution
    weight for personalized PageRank. Two independent sources:
      - every wallet in a Tier-2 flagged peeling chain, weight = chain
        detector's own confidence score
      - wallets identified via network-fusion's receiving-side IP
        fingerprint as a likely ransomware collector, weight = 0.9 fixed
        (binary detector, no graded confidence currently)
    """
    seeds = defaultdict(float)

    for chain in flagged_chains:
        for w in chain["chain_wallets"]:
            seeds[w] = max(seeds[w], chain["confidence"])
        for w in chain.get("peel_sink_wallets", []):
            # Cash-out endpoint, not a laundering hop — real evidence,
            # but discounted relative to actual chain membership.
            seeds[w] = max(seeds[w], round(chain["confidence"] * 0.75, 4))

    for sweep in (flagged_sweeps or []):
        for w in sweep["wallets"]:
            seeds[w] = max(seeds[w], sweep["confidence"])

    # receiving-side ransomware fingerprint, re-derived directly (not
    # imported from the evaluator, which only returns aggregate counts)
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

    for wallet, sender_ip_map in inbound_by_recipient.items():
        if len(sender_ip_map) < 3:
            continue
        ips = list(sender_ip_map.values())
        most_common_count = max(ips.count(ip) for ip in set(ips))
        if most_common_count >= 3:
            seeds[wallet] = max(seeds[wallet], 0.9)

    if enable_ip_crossref:
        _apply_ip_crossref_seeds(seeds, inbound_by_recipient)

    return dict(seeds)


IP_CROSSREF_CONFIDENCE = 0.6  # deliberately below every other seed source —
                               # single-observation signal, kept subordinate
                               # to chain/sweep/multi-sender evidence so it
                               # can't dominate CRITICAL-tier precision.


def _apply_ip_crossref_seeds(seeds, inbound_by_recipient):
    """
    Second-pass seeding for wallets invisible to the multi-sender
    fingerprint because they only appear in ONE observed incoming tx
    (structurally impossible to clear a >=3-sender threshold). Instead
    of requiring reuse WITHIN this wallet's own history, checks whether
    this wallet's single relay IP is shared with infrastructure already
    implicated by an independent detector (chain, peel-sink, sweep, or
    the existing multi-sender path) — i.e. cross-wallet infra reuse
    rather than within-wallet reuse. This mirrors Section 5.2's
    Network-Identity Fusion: infra fingerprint correlated across
    entities, not just within one.

    Mutates `seeds` in place. Only reads from already-seeded wallets and
    relay observations — never touches ground truth.
    """
    # Build IP -> set(already-seeded wallets relaying through it), from
    # the trusted anchor set established BEFORE this function runs.
    already_seeded = set(seeds.keys())
    ip_to_seeded_wallets = defaultdict(set)
    for wallet, sender_ip_map in inbound_by_recipient.items():
        if wallet not in already_seeded:
            continue
        for ip in sender_ip_map.values():
            ip_to_seeded_wallets[ip].add(wallet)

    for wallet, sender_ip_map in inbound_by_recipient.items():
        if wallet in seeds:
            continue  # already has independent evidence, don't downgrade it
        if len(sender_ip_map) >= 3:
            continue  # handled by the multi-sender path above; this pass
                       # is specifically for single/low-observation wallets
        for ip in sender_ip_map.values():
            linked = ip_to_seeded_wallets.get(ip, set()) - {wallet}
            if linked:
                seeds[wallet] = max(seeds.get(wallet, 0.0), IP_CROSSREF_CONFIDENCE)
                break


# ---------------------------------------------------------------------
# 3. Personalized PageRank (power iteration)
# ---------------------------------------------------------------------

def personalized_pagerank(out_edges, seeds, all_wallets, damping=DAMPING, iterations=PPR_ITERATIONS):
    n = len(all_wallets)
    if n == 0:
        return {}

    seed_total = sum(seeds.values())
    if seed_total == 0:
        restart = {w: 1.0 / n for w in all_wallets}
    else:
        restart = {w: (seeds.get(w, 0.0) / seed_total) for w in all_wallets}

    # row-normalized transition weights
    norm_edges = {}
    for src, dests in out_edges.items():
        total = sum(dests.values())
        if total > 0:
            norm_edges[src] = {d: w / total for d, w in dests.items()}

    r = dict(restart)
    for _ in range(iterations):
        next_r = defaultdict(float)
        dangling_mass = 0.0
        for w in all_wallets:
            score = r.get(w, 0.0)
            dests = norm_edges.get(w)
            if not dests:
                dangling_mass += score  # no outgoing edges — redistribute via restart
                continue
            for dest, weight in dests.items():
                next_r[dest] += damping * score * weight

        for w in all_wallets:
            next_r[w] = next_r.get(w, 0.0) + (1 - damping) * restart[w] + damping * dangling_mass * restart[w]

        total = sum(next_r.values())
        if total > 0:
            r = {w: next_r[w] / total for w in all_wallets}
        else:
            r = next_r

    return r


# ---------------------------------------------------------------------
# 4. Final score blend + tiering
# ---------------------------------------------------------------------

def classify_tier(score):
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "CLEAR"


def compute_risk_ratio(seeded_ppr, baseline_ppr, all_wallets, epsilon=1e-12):
    """
    seeded_ppr / baseline_ppr per wallet. baseline_ppr is PageRank with a
    UNIFORM restart (no seeds) — a wallet's natural structural importance
    from being well-connected, independent of any risk signal. seeded_ppr
    alone is dominated by the same hub effect (a busy legit_business has
    high seeded PPR simply because it has high baseline PPR, not because
    it is near a seed) — confirmed directly: raw-PPR percentile-ranking
    put 1144 wallets in MEDIUM with only 4.7% actually illicit, because in
    a 12,294-wallet graph with damping=0.85, mass diffuses widely enough
    that "more mass than most" stops meaning "near a seed" and starts
    meaning "well-connected in general".

    The ratio isolates the EXTRA mass a wallet gets specifically because
    of the seeds: ratio ~= 1 means "got its fair baseline share, nothing
    more"; ratio >> 1 means "seeds are pulling risk toward this wallet
    well beyond its natural graph position".
    """
    ratios = {}
    for w in all_wallets:
        base = baseline_ppr.get(w, epsilon)
        seeded = seeded_ppr.get(w, 0.0)
        ratios[w] = seeded / max(base, epsilon)
    return ratios


def compute_final_scores(seeds, risk_ratios, all_wallets):
    """
    Blend: 60% direct detector evidence (seed confidence, 0 if not
    directly flagged) + 40% propagated exposure (risk_ratio, percentile
    ranked across the wallet universe). Weighting favors direct evidence
    since our detectors are independently validated at 1.0 precision/recall
    on their own turf — propagation exists to extend reach to wallets the
    direct detectors don't touch, not to override them.
    """
    if risk_ratios:
        sorted_wallets = sorted(risk_ratios.items(), key=lambda x: x[1])
        n = len(sorted_wallets)
        percentile = {w: (i / (n - 1) if n > 1 else 1.0) for i, (w, v) in enumerate(sorted_wallets)}
    else:
        percentile = {}

    results = []
    for w in all_wallets:
        direct = seeds.get(w, 0.0) * 100
        ppr_norm = percentile.get(w, 0.0) * 100
        final = round(0.6 * direct + 0.4 * ppr_norm, 2)
        results.append({
            "wallet": w,
            "direct_evidence_score": round(direct, 2),
            "propagated_score": round(ppr_norm, 2),
            "final_score": final,
            "tier": classify_tier(final),
        })
    results.sort(key=lambda r: r["final_score"], reverse=True)
    return results


# ---------------------------------------------------------------------
# 5. Evaluation against is_illicit ground truth
# ---------------------------------------------------------------------

def evaluate_against_ground_truth(scored_results, ground_truth_path):
    gt = json.load(open(ground_truth_path))
    wallet_to_illicit = {}
    for g in gt:
        for w in g["wallets"]:
            wallet_to_illicit[w] = g["is_illicit"]

    tier_stats = defaultdict(lambda: {"illicit": 0, "total": 0})
    for r in scored_results:
        truth = wallet_to_illicit.get(r["wallet"])
        if truth is None:
            continue
        tier_stats[r["tier"]]["total"] += 1
        if truth:
            tier_stats[r["tier"]]["illicit"] += 1

    tier_precision = {}
    for tier, stats in tier_stats.items():
        tier_precision[tier] = {
            "flagged_wallets": stats["total"],
            "actually_illicit": stats["illicit"],
            "precision": round(stats["illicit"] / stats["total"], 4) if stats["total"] else None,
        }

    total_illicit = sum(1 for v in wallet_to_illicit.values() if v)
    critical_and_high = sum(1 for r in scored_results if r["tier"] in ("CRITICAL", "HIGH")
                             and wallet_to_illicit.get(r["wallet"]))
    recall_at_high_plus = round(critical_and_high / total_illicit, 4) if total_illicit else None

    return {
        "tier_precision": tier_precision,
        "total_illicit_wallets_in_dataset": total_illicit,
        "illicit_recall_at_CRITICAL_or_HIGH": recall_at_high_plus,
    }


if __name__ == "__main__":
    tx_map = load_transactions("dataset/output/bitcoin_transactions.csv")
    relay_map = load_relay_map("dataset/output/relay_events.csv")
    flagged_chains, _ = detect_peeling_chains("dataset/output/bitcoin_transactions.csv")
    flagged_sweeps = detect_darknet_sweeps("dataset/output/bitcoin_transactions.csv", relay_map)

    all_wallets = set()
    for data in tx_map.values():
        for w, a, t in data["inputs"] + data["outputs"]:
            all_wallets.add(w)

    seeds = build_seeds(tx_map, relay_map, flagged_chains, "dataset/output/ground_truth.json", flagged_sweeps=flagged_sweeps)
    print(f"Total wallets in graph: {len(all_wallets)}")
    print(f"Seed wallets (direct detector hits): {len(seeds)}")
    print(f"  from sweeps: {len(flagged_sweeps)} flagged sweeps feeding seeds")

    out_edges = build_wallet_graph(tx_map)
    ppr_scores = personalized_pagerank(out_edges, seeds, all_wallets)
    baseline_scores = personalized_pagerank(out_edges, {}, all_wallets)  # empty seeds -> uniform restart
    risk_ratios = compute_risk_ratio(ppr_scores, baseline_scores, all_wallets)

    scored = compute_final_scores(seeds, risk_ratios, all_wallets)

    print(f"\nTop 10 highest-risk wallets:")
    for r in scored[:10]:
        print(f"  {r['wallet'][:20]}...  tier={r['tier']:8s}  final={r['final_score']:6.2f}  "
              f"(direct={r['direct_evidence_score']:.1f}, propagated={r['propagated_score']:.1f})")

    eval_result = evaluate_against_ground_truth(scored, "dataset/output/ground_truth.json")
    print(f"\nEvaluation against is_illicit ground truth:")
    print(json.dumps(eval_result, indent=2))

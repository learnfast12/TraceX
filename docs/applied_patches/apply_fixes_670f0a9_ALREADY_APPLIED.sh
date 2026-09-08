#!/usr/bin/env bash
# TRACE-X — apply_fixes.sh
# Fix 1: peel_sink wallets are cash-out endpoints, structurally never a
#        `next_wallet` (they don't respend), so they never appear in
#        chain_wallets even though ground truth counts them as entity
#        members. Patch pattern_detection.py to track and report them
#        separately (peel_sink_wallets), tagged by role so downstream
#        consumers (risk_scoring, dashboard) know these are cash-out
#        points, not laundering hops — different investigative meaning.
#
# Fix 2: ransomware_collector wallets used in exactly one observed
#        incoming tx can never clear the existing 3-sender IP-reuse
#        threshold (structurally impossible with n=1). Add a second,
#        independent seed path in risk_scoring.py: cross-reference a
#        single-tx wallet's relay IP against the IP footprint of
#        wallets ALREADY seeded by other detectors (chains, sweeps,
#        multi-sender fingerprint). Reused infra = signal, even at n=1.
#        Seeded at reduced confidence (0.6) since it's a weaker,
#        single-observation signal — keeps CRITICAL-tier precision
#        intact while giving PPR something non-zero to propagate from.
#
# Run from repo root: bash apply_fixes.sh

set -euo pipefail
cd "$(dirname "$0")" 2>/dev/null || true

echo "=== [1/3] Patching pattern_detection.py: track peel_sink membership ==="
python3 << 'EOF'
path = "backend/pattern_detection.py"
src = open(path).read()

old_walk = '''def walk_chains(hop_from):
    """
    Chains together consecutive hops: wallet A -> next_wallet B (via one
    hop) -> next_wallet C (via another hop) -> ... Chain roots are wallets
    that START a hop but are never themselves a next_wallet of another hop
    (i.e., nothing feeds into them from an earlier peel).
    """
    is_next_wallet = set(h["next_wallet"] for h in hop_from.values())
    roots = [w for w in hop_from if w not in is_next_wallet]

    chains = []
    for root in roots:
        chain_wallets = [root]
        chain_hops = []
        current = root
        seen = {root}
        while current in hop_from:
            hop = hop_from[current]
            chain_hops.append(hop)
            nxt = hop["next_wallet"]
            if nxt in seen:
                break  # guard against any accidental cycle
            chain_wallets.append(nxt)
            seen.add(nxt)
            current = nxt
        chains.append({"wallets": chain_wallets, "hops": chain_hops})
    return chains'''

new_walk = '''def walk_chains(hop_from):
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
    return chains'''

assert src.count(old_walk) == 1, f"walk_chains match: {src.count(old_walk)}"
src = src.replace(old_walk, new_walk)

old_detect = '''    flagged = []
    for chain in all_chains:
        if len(chain["hops"]) < MIN_CHAIN_HOPS:
            continue
        confidence = score_chain(chain)
        flagged.append({
            "chain_wallets": chain["wallets"],
            "hop_count": len(chain["hops"]),
            "avg_skew_ratio": round(statistics.mean(h["skew_ratio"] for h in chain["hops"]), 4),
            "txids": [h["txid"] for h in chain["hops"]],
            "confidence": confidence,
        })'''

new_detect = '''    flagged = []
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
        })'''

assert src.count(old_detect) == 1, f"detect_peeling_chains match: {src.count(old_detect)}"
src = src.replace(old_detect, new_detect)

open(path, "w").write(src)
print("[OK] pattern_detection.py: peel_sink_wallets now tracked per-chain")
EOF

echo -e "\n=== [2/3] Patching risk_scoring.py: seed peel sinks + IP cross-reference for single-tx wallets ==="
python3 << 'EOF'
path = "backend/risk_scoring.py"
src = open(path).read()

# --- 2a. seed peel_sink_wallets alongside chain_wallets, at reduced
#     confidence — a cash-out endpoint is real evidence but weaker than
#     being an actual laundering hop, so it shouldn't outrank hop members
#     in tie-breaks. 0.75x the chain's own confidence.
old_loop = '''    for chain in flagged_chains:
        for w in chain["chain_wallets"]:
            seeds[w] = max(seeds[w], chain["confidence"])

    for sweep in (flagged_sweeps or []):'''

new_loop = '''    for chain in flagged_chains:
        for w in chain["chain_wallets"]:
            seeds[w] = max(seeds[w], chain["confidence"])
        for w in chain.get("peel_sink_wallets", []):
            # Cash-out endpoint, not a laundering hop — real evidence,
            # but discounted relative to actual chain membership.
            seeds[w] = max(seeds[w], round(chain["confidence"] * 0.75, 4))

    for sweep in (flagged_sweeps or []):'''

assert src.count(old_loop) == 1, f"peel_sink seed loop match: {src.count(old_loop)}"
src = src.replace(old_loop, new_loop)

# --- 2b. IP cross-reference pass for single-observation wallets that
#     can't clear the existing multi-sender threshold. Runs AFTER the
#     primary seed set is built (chains + peel sinks + sweeps + the
#     existing multi-sender fingerprint), and only uses seeds already
#     established by those independent detectors as the trusted anchor
#     set — never touches ground truth. If a wallet's single relay IP
#     matches the relay IP of ANY already-seeded wallet, that's shared
#     infrastructure — a real signal even from one observation.
old_sig = '''def build_seeds(tx_map, relay_map, flagged_chains, ground_truth_path_for_wallet_universe, flagged_sweeps=None):'''
new_sig = '''def build_seeds(tx_map, relay_map, flagged_chains, ground_truth_path_for_wallet_universe, flagged_sweeps=None, enable_ip_crossref=True):'''
assert src.count(old_sig) == 1, f"sig match: {src.count(old_sig)}"
src = src.replace(old_sig, new_sig)

old_return = '''    for wallet, sender_ip_map in inbound_by_recipient.items():
        if len(sender_ip_map) < 3:
            continue
        ips = list(sender_ip_map.values())
        most_common_count = max(ips.count(ip) for ip in set(ips))
        if most_common_count >= 3:
            seeds[wallet] = max(seeds[wallet], 0.9)

    return dict(seeds)'''

new_return = '''    for wallet, sender_ip_map in inbound_by_recipient.items():
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
                break'''

assert src.count(old_return) == 1, f"return-block match: {src.count(old_return)}"
src = src.replace(old_return, new_return)

open(path, "w").write(src)
print("[OK] risk_scoring.py: peel-sink seeding + IP cross-reference pass added")
EOF

echo -e "\n=== [3/3] Re-running full evaluation ==="
python3 << 'EOF'
import sys, json
sys.path.insert(0, "backend")
from clustering import load_transactions
from pattern_detection import detect_peeling_chains
from network_fusion import load_relay_map
from convergence_detection import detect_darknet_sweeps
from risk_scoring import build_seeds

tx_map = load_transactions("dataset/output/bitcoin_transactions.csv")
relay_map = load_relay_map("dataset/output/relay_events.csv")
flagged_chains, _ = detect_peeling_chains("dataset/output/bitcoin_transactions.csv")
flagged_sweeps = detect_darknet_sweeps("dataset/output/bitcoin_transactions.csv", relay_map)

seeds_before = build_seeds(tx_map, relay_map, flagged_chains, "dataset/output/ground_truth.json",
                            flagged_sweeps=flagged_sweeps, enable_ip_crossref=False)
seeds_after = build_seeds(tx_map, relay_map, flagged_chains, "dataset/output/ground_truth.json",
                           flagged_sweeps=flagged_sweeps, enable_ip_crossref=True)

gt = json.load(open("dataset/output/ground_truth.json"))
illicit_wallets = set()
by_type_total = {}
for e in gt:
    if e.get("is_illicit"):
        illicit_wallets.update(e["wallets"])
        by_type_total.setdefault(e["entity_type"], 0)
        by_type_total[e["entity_type"]] += len(e["wallets"])

wallet_type = {}
for e in gt:
    for w in e.get("wallets", []):
        wallet_type[w] = e.get("entity_type")

caught_before = {w for w in illicit_wallets if seeds_before.get(w, 0.0) > 0}
caught_after = {w for w in illicit_wallets if seeds_after.get(w, 0.0) > 0}

print(f"Total illicit wallets: {len(illicit_wallets)}")
print(f"Recall BEFORE this patch (chains+peel_sink+sweeps, no crossref): "
      f"{len(caught_before)}  ({len(caught_before)/len(illicit_wallets):.4f})")
print(f"Recall AFTER this patch (+ peel_sink seeding + IP crossref):     "
      f"{len(caught_after)}  ({len(caught_after)/len(illicit_wallets):.4f})")

still_missed = illicit_wallets - caught_after
print(f"\nStill missed: {len(still_missed)}")
by_type_missed = {}
for w in still_missed:
    t = wallet_type.get(w, "unknown")
    by_type_missed[t] = by_type_missed.get(t, 0) + 1
for t, n in sorted(by_type_missed.items(), key=lambda x: -x[1]):
    print(f"  {t}: {n} / {by_type_total.get(t)}")

newly_caught = caught_after - caught_before
print(f"\nNewly caught by this patch: {len(newly_caught)}")
by_type_new = {}
for w in newly_caught:
    t = wallet_type.get(w, "unknown")
    by_type_new[t] = by_type_new.get(t, 0) + 1
for t, n in sorted(by_type_new.items(), key=lambda x: -x[1]):
    print(f"  {t}: +{n}")
EOF

echo -e "\n=== Done. Also re-run risk_scoring.py directly to confirm tier precision didn't regress ==="
echo "    python3 backend/risk_scoring.py 2>&1 | tail -20"

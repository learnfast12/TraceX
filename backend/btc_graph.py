"""
Wallet/transaction graph builder for the Spider Map — Bitcoin domain.
Node tier_role comes from real peeling-chain hop position / darknet-sweep
membership, and risk comes from risk_scoring.py's real final_score/tier.
No wallet-address string matching anywhere.
"""

ROLE_SEVERITY = {
    "source": 0, "hop": 1, "peel_sink": 2,
    "sweep_input": 1, "sweep_vault": 3, "sink": 3,
}


def build_btc_graph_data(btc_cache):
    flagged_chains = btc_cache.get("flagged_chains", [])
    flagged_sweeps = btc_cache.get("flagged_sweeps", [])
    scored_by_wallet = btc_cache.get("scored_by_wallet", {})

    nodes = {}
    edges = []

    def get_risk(wallet):
        score = scored_by_wallet.get(wallet)
        if not score:
            return {"level": "CLEAR", "score": 0.0}
        level = score.get("tier") or score.get("risk_level") or "CLEAR"
        val = score.get("final_score", score.get("score", 0.0))
        return {"level": level, "score": val}

    def add_node(wallet, tier_role):
        if wallet not in nodes:
            nodes[wallet] = {"id": wallet, "risk": get_risk(wallet), "tier_role": tier_role}
        elif ROLE_SEVERITY.get(tier_role, 1) > ROLE_SEVERITY.get(nodes[wallet]["tier_role"], 1):
            nodes[wallet]["tier_role"] = tier_role

    # ── Peeling chains ──────────────────────────────────────────
    for chain in flagged_chains:
        wallets = chain.get("chain_wallets", [])
        hops = chain.get("hops", [])
        if not wallets:
            continue

        add_node(wallets[0], "source")
        for i, w in enumerate(wallets):
            add_node(w, "sink" if i == len(wallets) - 1 else "hop")

        for i, hop in enumerate(hops):
            if i >= len(wallets):
                continue
            src = wallets[i]
            nxt = hop.get("next_wallet")
            sink = hop.get("peel_sink")
            if nxt:
                edges.append({
                    "source": src, "target": nxt,
                    "amount": hop.get("remainder_amount", 0),
                    "transfer_type": "CHAIN_CONTINUE",
                })
            if sink:
                add_node(sink, "peel_sink")
                edges.append({
                    "source": src, "target": sink,
                    "amount": hop.get("peeled_amount", 0),
                    "transfer_type": "PEELED_OFF",
                })

    # ── Darknet sweeps ──────────────────────────────────────────
    for sweep in flagged_sweeps:
        vault = sweep.get("vault_wallet")
        inputs = sweep.get("input_wallets", [])
        if not vault:
            continue
        add_node(vault, "sweep_vault")
        for w in inputs:
            add_node(w, "sweep_input")
            edges.append({
                "source": w, "target": vault,
                "amount": sweep.get("total_amount"),  # None until convergence_detection.py patch below
                "transfer_type": "SWEEP_CONVERGE",
            })

    return {"nodes": list(nodes.values()), "edges": edges}

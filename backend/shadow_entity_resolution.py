"""
shadow_entity_resolution.py — TRACE-X Shadow Entity Resolution module.

Goal: detect wallets controlled by the same real-world actor that Union-Find
common-input clustering structurally cannot merge (e.g. a launderer using a
fresh wallet per hop, never co-spending inputs). We do this by behavioral
fingerprinting + embedding + density clustering + nearest-neighbor shadow
matching, independent of any on-chain co-spend signal.

SCHEMA ASSUMPTIONS (confirmed from network_fusion.py / main.py in this repo):
  - tx_map[txid]["inputs"]  -> list of (wallet, amount, ts) tuples
  - tx_map[txid]["outputs"] -> list of (wallet, amount, ts) tuples
  - relay_map[txid]         -> src_ip (str)
  - btc_cache["anomaly_features"] -> pandas DataFrame indexed by wallet,
    already computed by btc_anomaly.py (reused here as a base feature set
    rather than recomputed, so the two modules stay consistent)

Degrades gracefully: works with cosine-similarity-only matching if torch is
absent, and with numpy brute-force NN search if faiss is absent — never
crashes the app if optional deps are missing.
"""

import numpy as np
import pandas as pd
from collections import defaultdict

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

try:
    import hdbscan
    _HAS_HDBSCAN = True
except ImportError:
    _HAS_HDBSCAN = False

try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False


# ──────────────────────────────────────────────────────────────────────────
# 1. Behavioral fingerprint extraction
# ──────────────────────────────────────────────────────────────────────────

def build_behavioral_fingerprints(tx_map: dict, relay_map: dict,
                                   anomaly_features: pd.DataFrame = None) -> pd.DataFrame:
    """
    Per-wallet behavioral fingerprint, independent of address identity —
    the whole point is these features should look similar for two DIFFERENT
    wallet strings if one actor is rotating addresses.

    Features (chosen to be rotation-invariant, i.e. survive the actor
    switching to a brand-new wallet string):
      - inter_tx_interval_mean/std : timing signature (a script/actor has a
        characteristic cadence that survives address rotation)
      - amount_entropy             : how varied the actor's tx amounts are
      - round_number_ratio         : fraction of amounts that are "round"
        (manual actors round; scripts often don't, or round differently)
      - fanout_ratio                : avg outputs per tx (peeling vs. sweep
        vs. simple-spend behavioral signature)
      - relay_ip_reuse              : whether this wallet's broadcasts share
        src_ip with other wallets (strong same-operator signal — reused as
        a *feature* here, not just a hard link, so it blends with the rest)
      - hour_of_day_concentration   : operational-hours fingerprint
    """
    per_wallet_events = defaultdict(list)  # wallet -> list of (ts_epoch_seconds, amount, role, ip)

    def _to_epoch(ts):
        # tx_map timestamps come in as ISO-8601 strings (e.g.
        # '2025-11-03T17:00:00'), not unix floats — normalize once here so
        # every downstream computation can assume float epoch seconds.
        if isinstance(ts, (int, float)):
            return float(ts)
        return pd.Timestamp(ts).timestamp()

    for txid, data in tx_map.items():
        ip = relay_map.get(txid)
        for wallet, amount, ts in data.get("inputs", []):
            per_wallet_events[wallet].append((_to_epoch(ts), amount, "in", ip))
        for wallet, amount, ts in data.get("outputs", []):
            per_wallet_events[wallet].append((_to_epoch(ts), amount, "out", ip))

    rows = []
    wallet_ips = defaultdict(set)
    for w, events in per_wallet_events.items():
        for _, _, _, ip in events:
            if ip:
                wallet_ips[w].add(ip)

    # IP reuse across wallets — computed once, globally, then looked up per wallet
    ip_to_wallets = defaultdict(set)
    for w, ips in wallet_ips.items():
        for ip in ips:
            ip_to_wallets[ip].add(w)

    for w, events in per_wallet_events.items():
        events.sort(key=lambda e: e[0])
        timestamps = np.array([e[0] for e in events], dtype=float)
        amounts = np.array([e[1] for e in events], dtype=float)
        out_count = sum(1 for e in events if e[2] == "out")
        tx_count = max(len(events), 1)

        if len(timestamps) > 1:
            intervals = np.diff(timestamps)
            interval_mean = float(np.mean(intervals))
            interval_std = float(np.std(intervals))
        else:
            interval_mean = 0.0
            interval_std = 0.0

        if len(amounts) > 0 and amounts.sum() > 0:
            probs = amounts / amounts.sum()
            amount_entropy = float(-(probs * np.log2(probs + 1e-12)).sum())
        else:
            amount_entropy = 0.0

        round_ratio = float(np.mean([1.0 if (a > 0 and round(a, 4) == round(a, 2)) else 0.0
                                      for a in amounts])) if len(amounts) else 0.0

        fanout_ratio = out_count / tx_count

        shared_ip_wallets = set()
        for ip in wallet_ips.get(w, []):
            shared_ip_wallets |= ip_to_wallets[ip]
        shared_ip_wallets.discard(w)
        ip_reuse_degree = len(shared_ip_wallets)

        if len(timestamps) > 0:
            hours = (timestamps.astype(np.int64) // 3600) % 24
            hour_counts = np.bincount(hours.astype(int), minlength=24)
            hour_probs = hour_counts / max(hour_counts.sum(), 1)
            hour_concentration = float((hour_probs ** 2).sum())  # Herfindahl index — 1.0 = single hour, low = spread out
        else:
            hour_concentration = 0.0

        rows.append({
            "wallet": w,
            "sef_event_count": len(events),
            "sef_interval_mean": interval_mean,
            "sef_interval_std": interval_std,
            "sef_amount_entropy": amount_entropy,
            "sef_round_ratio": round_ratio,
            "sef_fanout_ratio": fanout_ratio,
            "sef_ip_reuse_degree": ip_reuse_degree,
            "sef_hour_concentration": hour_concentration,
        })

    fp = pd.DataFrame(rows).set_index("wallet")

    if anomaly_features is not None:
        # Blend in the existing anomaly feature set (already numeric, already
        # per-wallet) so the fingerprint also carries volume/degree signal
        # without recomputing it — keeps the two modules' features consistent.
        shared_cols = [c for c in anomaly_features.columns if c not in fp.columns]
        fp = fp.join(anomaly_features[shared_cols], how="left").fillna(0.0)

    return fp


# ──────────────────────────────────────────────────────────────────────────
# 2. Embedding — contrastive-style projector if torch available, else scaled PCA
# ──────────────────────────────────────────────────────────────────────────

class _ProjectionHead(nn.Module if _HAS_TORCH else object):
    """Small MLP projecting fingerprints into a shadow-matching embedding
    space. Trained with a lightweight self-supervised objective: pull
    together jittered views of the SAME wallet's fingerprint (positive
    pairs), push apart random other wallets (negative pairs) — a
    simplified SimCLR-style contrastive setup appropriate for a tabular,
    non-image feature set with no labeled entity-identity ground truth."""

    def __init__(self, in_dim, embed_dim=16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 32), nn.ReLU(),
            nn.Linear(32, embed_dim),
        )

    def forward(self, x):
        z = self.net(x)
        return z / (z.norm(dim=1, keepdim=True) + 1e-8)


def _train_contrastive_embedding(X: np.ndarray, embed_dim=16, epochs=40, lr=1e-3, seed=42) -> np.ndarray:
    torch.manual_seed(seed)
    Xt = torch.tensor(X, dtype=torch.float32)
    model = _ProjectionHead(X.shape[1], embed_dim)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    n = Xt.shape[0]
    batch = min(256, n)

    for _ in range(epochs):
        idx = torch.randperm(n)[:batch]
        anchor = Xt[idx]
        # jitter = positive view of the same wallet (simulates address
        # rotation adding small behavioral noise, not identity change)
        jitter = anchor + 0.05 * torch.randn_like(anchor)

        z1 = model(anchor)
        z2 = model(jitter)

        sim = z1 @ z2.T / 0.1  # temperature-scaled cosine similarity matrix
        labels = torch.arange(batch)
        loss = nn.functional.cross_entropy(sim, labels)

        opt.zero_grad()
        loss.backward()
        opt.step()

    with torch.no_grad():
        return model(Xt).numpy()


def embed_fingerprints(fp: pd.DataFrame, embed_dim: int = 16) -> np.ndarray:
    X = fp.values.astype(np.float64)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)  # standardize first, always
    X = np.nan_to_num(X)

    if _HAS_TORCH and len(fp) >= 20:
        return _train_contrastive_embedding(X, embed_dim=embed_dim)

    # Fallback: PCA-via-SVD projection — no learned contrastive structure,
    # but still a sane dense embedding for clustering/NN search.
    U, S, Vt = np.linalg.svd(X - X.mean(axis=0), full_matrices=False)
    k = min(embed_dim, Vt.shape[0])
    return (U[:, :k] * S[:k])


# ──────────────────────────────────────────────────────────────────────────
# 3. Clustering + shadow-match nearest-neighbor search
# ──────────────────────────────────────────────────────────────────────────

def cluster_shadow_entities(embeddings: np.ndarray, min_cluster_size: int = 3):
    if _HAS_HDBSCAN:
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
        labels = clusterer.fit_predict(embeddings)
        probs = getattr(clusterer, "probabilities_", np.ones(len(labels)))
        return labels, probs

    # Fallback: simple agglomerative-ish clustering via distance threshold,
    # so the endpoint still returns something meaningful without hdbscan.
    from scipy.cluster.hierarchy import fcluster, linkage
    Z = linkage(embeddings, method="average")
    labels = fcluster(Z, t=1.5, criterion="distance") - 1  # 0-indexed like hdbscan
    return labels, np.ones(len(labels))


def estimate_similarity_threshold(norm_emb: np.ndarray, percentile: float = 99.5,
                                   sample_size: int = 200000, seed: int = 42) -> dict:
    """Data-driven threshold from this dataset's own pairwise-similarity distribution."""
    rng = np.random.default_rng(seed)
    n = norm_emb.shape[0]
    n_pairs = min(sample_size, max(1, n * (n - 1) // 2))
    i = rng.integers(0, n, size=n_pairs)
    j = rng.integers(0, n, size=n_pairs)
    mask = i != j
    i, j = i[mask], j[mask]
    sims = np.einsum("ij,ij->i", norm_emb[i], norm_emb[j])
    threshold = float(np.percentile(sims, percentile))
    return {
        "threshold": threshold,
        "baseline_mean": float(sims.mean()),
        "baseline_std": float(sims.std()),
        "baseline_p50": float(np.percentile(sims, 50)),
        "baseline_p99": float(np.percentile(sims, 99)),
        "percentile_used": percentile,
        "n_pairs_sampled": int(len(sims)),
    }


def find_shadow_matches(fp: pd.DataFrame, embeddings: np.ndarray, k: int = 5,
                         similarity_threshold: float = None,
                         auto_percentile: float = 99.5):
    """
    For each wallet, find its top-k nearest neighbors in embedding space.
    A shadow match is a pair whose similarity sits in the extreme tail of
    this dataset's own pairwise-similarity distribution — not an absolute
    number — since within-archetype wallets are already behaviorally close
    by construction. Pass similarity_threshold to override auto-estimation.
    """
    wallets = fp.index.to_numpy()
    n = len(wallets)
    norm_emb = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

    diagnostics = estimate_similarity_threshold(norm_emb, percentile=auto_percentile)
    threshold = similarity_threshold if similarity_threshold is not None else diagnostics["threshold"]

    if _HAS_FAISS and n >= 50:
        index = faiss.IndexFlatIP(norm_emb.shape[1])
        index.add(norm_emb.astype(np.float32))
        sims, idxs = index.search(norm_emb.astype(np.float32), min(k + 1, n))
    else:
        sim_matrix = norm_emb @ norm_emb.T
        idxs = np.argsort(-sim_matrix, axis=1)[:, :k + 1]
        sims = np.take_along_axis(sim_matrix, idxs, axis=1)

    matches = defaultdict(list)
    for i in range(n):
        for j, s in zip(idxs[i], sims[i]):
            if j == i or j < 0:
                continue
            if s >= threshold:
                matches[wallets[i]].append({"wallet": wallets[j], "similarity": round(float(s), 4)})

    diagnostics["threshold_used"] = threshold
    diagnostics["wallets_with_matches"] = len(matches)
    return dict(matches), diagnostics


# ──────────────────────────────────────────────────────────────────────────
# 4. Orchestration entrypoint — called once at startup, cached like the rest
# ──────────────────────────────────────────────────────────────────────────

def run_shadow_entity_resolution(tx_map: dict, relay_map: dict,
                                  anomaly_features: pd.DataFrame = None,
                                  min_cluster_size: int = 3,
                                  similarity_threshold: float = None,
                                  auto_percentile: float = 99.5,
                                  min_events: int = 3) -> dict:
    fp_all = build_behavioral_fingerprints(tx_map, relay_map, anomaly_features)

    if len(fp_all) < 5:
        return {"fingerprints": fp_all, "embeddings": None, "cluster_labels": {},
                "shadow_matches": {}, "diagnostics": {}, "backend": "insufficient_data"}

    # Wallets with too few events (default <3) have no reliable behavioral
    # signal — a single transaction can't establish a timing/entropy
    # fingerprint. Including them collapses the embedding space (near-
    # identical degenerate vectors get treated as "similar"). Exclude them
    # from matching and report them separately instead of silently
    # clustering on noise.
    eligible_mask = fp_all["sef_event_count"] >= min_events
    fp = fp_all[eligible_mask]
    excluded_wallets = fp_all.index[~eligible_mask].tolist()

    if len(fp) < 5:
        return {"fingerprints": fp_all, "embeddings": None, "cluster_labels": {},
                "shadow_matches": {},
                "diagnostics": {"excluded_low_event_wallets": len(excluded_wallets)},
                "backend": "insufficient_data"}

    embeddings = embed_fingerprints(fp)
    labels, probs = cluster_shadow_entities(embeddings, min_cluster_size=min_cluster_size)
    shadow_matches, diagnostics = find_shadow_matches(
        fp, embeddings, similarity_threshold=similarity_threshold, auto_percentile=auto_percentile
    )
    diagnostics["excluded_low_event_wallets"] = len(excluded_wallets)
    diagnostics["min_events_required"] = min_events
    diagnostics["eligible_wallets"] = len(fp)

    cluster_labels = {w: int(l) for w, l in zip(fp.index, labels)}
    cluster_probs = {w: round(float(p), 4) for w, p in zip(fp.index, probs)}

    return {
        "fingerprints": fp_all,
        "embeddings": embeddings,
        "cluster_labels": cluster_labels,
        "cluster_probs": cluster_probs,
        "shadow_matches": shadow_matches,
        "excluded_wallets": excluded_wallets,
        "diagnostics": diagnostics,
        "backend": ("torch+hdbscan+faiss" if (_HAS_TORCH and _HAS_HDBSCAN and _HAS_FAISS)
                    else "fallback(svd/scipy/bruteforce)"),
    }

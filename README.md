# TRACE-X

**AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic**
SIH 2026 · Problem Statement 26146 · Organisation: NTRO
Team OMEGA 404 · Sri Sairam Engineering College, Dept. of CSE (Cybersecurity)

Offline, air-gapped Bitcoin transaction intelligence platform fusing
network-layer telemetry (IP/port/timing) with blockchain-layer data
(wallets, TXIDs, amounts) to detect, cluster, score, and explain illicit
Bitcoin activity. Forked and retargeted from **TraceNetX** (banking/mule-account
domain, validated on Bank of India CyberShield data) to the Bitcoin UTXO domain.

Full architecture and detection-logic writeup: [`docs/solution-approach.md`](docs/solution-approach.md)

## Quick start

```bash
# 1. Generate the synthetic dataset (deterministic, seed=42)
cd dataset && python3 generator.py && cd ..

# 2. Install backend deps
pip install -r backend/requirements.txt

# 3. Run validation (recall / precision against ground truth)
python3 backend/risk_scoring.py

# 4. Start the API (see start-tracenetx-v2.sh for the full stack)
cd backend && uvicorn main:app --reload
```

## Current validated metrics

Synthetic dataset (deterministic regeneration, seed=42):

| Tier | Flagged | Actually illicit | Precision |
|---|---|---|---|
| CRITICAL | — | — | 1.0 |
| HIGH | — | — | 1.0 |
| MEDIUM | — | 0 | 0.0 (clean separation) |
| CLEAR | — | 0 | 0.0 (clean separation) |

Illicit wallet recall (CRITICAL+HIGH): **1.0000** (post generator-coverage fix)

External validation on the [Elliptic dataset](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set)
(temporal split matching Weber et al. 2019 — train steps 1–34, test steps 35–49):

| Model | Precision | Recall | F1 | AUPRC | AUROC |
|---|---|---|---|---|---|
| RandomForest | 0.90 | 0.72 | 0.80 | 0.799 | 0.941 |
| XGBoost | 0.81 | 0.74 | 0.77 | 0.804 | 0.938 |
| LightGBM | 0.80 | 0.74 | 0.77 | 0.798 | 0.926 |

RandomForest beats the paper's published RF baseline (~0.80 P / ~0.65 R / ~0.72 F1).
Full results: [`dataset/elliptic/elliptic_benchmark_results.csv`](dataset/elliptic/elliptic_benchmark_results.csv)

## Repo notes

- `dataset/output/` is **regeneratable, not committed** (see `.gitignore`) — run `dataset/generator.py`
  to reproduce it byte-for-byte (seed=42, fully deterministic as of `60e298e`/`546ac76`).
- `docs/applied_patches/` holds historical one-shot patch scripts — do not re-run, see its README.
- `docs/_tracenetx_reference/` holds the original TraceNetX reference material this fork was built from.

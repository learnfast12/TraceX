"""
models.py — Pydantic response schemas for the TRACE-X Bitcoin intelligence
API. Pulled out into its own module so main.py stays readable and so
/docs renders real typed schemas instead of opaque dict blobs.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Shared / error envelope
# ─────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ─────────────────────────────────────────────────────────────────
# /btc/status
# ─────────────────────────────────────────────────────────────────

class BtcStatus(BaseModel):
    status: str = Field(..., example="ONLINE")
    transactions_indexed: int
    wallets_indexed: int
    peeling_chains_flagged: int
    darknet_sweeps_flagged: int


# ─────────────────────────────────────────────────────────────────
# /btc/risk-scores, /btc/dashboard
# ─────────────────────────────────────────────────────────────────

class WalletRiskScore(BaseModel):
    wallet: str
    direct_evidence_score: float
    propagated_score: float
    final_score: float
    tier: str
    anomaly_score: Optional[float] = None
    ml_blended_score: Optional[float] = None
    geo_countries: list[str] = []
    asns: list[str] = []


class RiskScoresResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: Optional[int] = None
    results: list[WalletRiskScore]


class DashboardResponse(BaseModel):
    total_wallets: int
    tier_breakdown: dict[str, int]
    top_10_critical: list[WalletRiskScore]
    peeling_chains_flagged: int
    darknet_sweeps_flagged: int


# ─────────────────────────────────────────────────────────────────
# /btc/peeling-chains, /btc/darknet-sweeps
# ─────────────────────────────────────────────────────────────────

class PeelingChain(BaseModel):
    chain_wallets: list[str]
    peel_sink_wallets: list[str]
    hop_count: int
    avg_skew_ratio: float
    txids: list[str]
    confidence: float


class PeelingChainsResponse(BaseModel):
    total: int
    limit: int
    has_more: bool
    results: list[PeelingChain]


class DarknetSweep(BaseModel):
    wallets: list[str]
    confidence: float
    # deliberately permissive beyond this — sweep shape varies by detector
    # version; strict typing here would break on legitimate schema drift.

    class Config:
        extra = "allow"


class DarknetSweepsResponse(BaseModel):
    total: int
    limit: int
    has_more: bool
    results: list[DarknetSweep]


# ─────────────────────────────────────────────────────────────────
# /btc/wallet/{wallet_id}
# ─────────────────────────────────────────────────────────────────

class WalletDetailResponse(BaseModel):
    wallet_id: str
    risk: Optional[WalletRiskScore] = None
    peeling_chain_membership: list[PeelingChain] = []
    darknet_sweep_membership: list[DarknetSweep] = []


# ─────────────────────────────────────────────────────────────────
# /btc/wallet/{wallet_id}/anomaly-explanation
# ─────────────────────────────────────────────────────────────────

class FeatureContribution(BaseModel):
    feature: str
    impact: float


class AnomalyExplanationResponse(BaseModel):
    wallet: str
    anomaly_score: float
    top_contributing_features: list[FeatureContribution]


# ─────────────────────────────────────────────────────────────────
# /btc/wallet/{wallet_id}/geo
# ─────────────────────────────────────────────────────────────────

class IpGeoInfo(BaseModel):
    ip: str
    geo_country: Optional[str] = None
    asn: Optional[str] = None
    asn_org: Optional[str] = None


class WalletGeoResponse(BaseModel):
    wallet: str
    sending_ips: list[IpGeoInfo] = []
    receiving_ips: list[IpGeoInfo] = []


# ─────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    btc_layer_loaded: bool

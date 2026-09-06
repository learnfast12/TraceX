"""
Digital Arrest Scam Detection Engine — PS6 module
Detects scam escalation stage from call/message transcripts + self-reported
caller metadata, BEFORE the video-call/payment stage — this is the
"lead time" differentiator PS6 explicitly scores on.

No telecom tracing, no location access, no contact-log access — this is a
content + self-reported-metadata classifier, the same model a citizen-facing
app or call-center analyst would legally use.

Stages (real-world escalation order):
  1. INITIAL_PRETEXT      - courier/KYC/SIM deactivation hook
  2. AUTHORITY_ESCALATION - claims to be CBI/ED/Customs/Police
  3. ISOLATION_PRESSURE   - "don't hang up", "don't tell anyone", surveillance claims
  4. PAYMENT_DEMAND       - asks for money transfer to "prove innocence"
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import re

router = APIRouter()

# India's actual verified cybercrime/govt helpline prefixes.
# A real deployment would pull this from TRAI/DoT's verified registry.
LEGIT_GOVT_PREFIXES = ("1800", "155260", "1930")

PHRASE_BANKS = {
    "INITIAL_PRETEXT": [
        "parcel", "courier", "customs", "sim card", "sim deactivat",
        "aadhaar", "kyc", "package contains", "illegal item", "narcotics found",
    ],
    "AUTHORITY_ESCALATION": [
        "cbi", "enforcement directorate", "narcotics control bureau", "ncb",
        "customs department", "cyber cell", "cyber crime branch",
        "case has been registered", "fir has been filed", "warrant",
        "i am officer", "this is inspector", "verify your identity with police",
    ],
    "ISOLATION_PRESSURE": [
        "do not disconnect", "don't hang up", "don't tell anyone",
        "don't tell your family", "under surveillance", "digital arrest",
        "house arrest", "stay on this call", "cannot leave", "being monitored",
        "confidential investigation", "do not inform",
    ],
    "PAYMENT_DEMAND": [
        "transfer the amount", "pay a fine", "refundable deposit",
        "verification fee", "send money to this account", "rtgs",
        "prove your innocence", "clear your name", "processing fee",
        "escrow account", "government account",
    ],
}

STAGE_ORDER = ["INITIAL_PRETEXT", "AUTHORITY_ESCALATION", "ISOLATION_PRESSURE", "PAYMENT_DEMAND"]
STAGE_WEIGHT = {"INITIAL_PRETEXT": 10, "AUTHORITY_ESCALATION": 25, "ISOLATION_PRESSURE": 35, "PAYMENT_DEMAND": 50}
STAGE_LABEL = {
    "INITIAL_PRETEXT": "Initial Pretext",
    "AUTHORITY_ESCALATION": "Authority Escalation",
    "ISOLATION_PRESSURE": "Isolation Pressure",
    "PAYMENT_DEMAND": "Payment Demand",
}


class TranscriptInput(BaseModel):
    transcript: str
    caller_number: Optional[str] = None
    claimed_authority: Optional[str] = None
    call_duration_minutes: Optional[float] = None


def scan_transcript(text: str):
    text_l = text.lower()
    matches = {}
    for stage, phrases in PHRASE_BANKS.items():
        hits = [p for p in phrases if p in text_l]
        if hits:
            matches[stage] = hits
    return matches


def score_caller_metadata(caller_number, claimed_authority):
    """Self-reported metadata only. Flags spoofed-authority signature:
    caller claims a government body but the number doesn't match any
    known legitimate prefix. No tracing, no carrier data."""
    if not caller_number or not claimed_authority:
        return 0, None
    is_legit_prefix = any(caller_number.startswith(p) for p in LEGIT_GOVT_PREFIXES)
    govt_claim = bool(re.search(r"cbi|ed|customs|police|narcotics|ncb", claimed_authority, re.I))
    if govt_claim and not is_legit_prefix:
        return 30, f"Claims '{claimed_authority}' but number does not match any verified government prefix"
    return 0, None


def analyze(payload: TranscriptInput):
    matches = scan_transcript(payload.transcript)
    highest_stage = None
    stage_score = 0
    for stage in STAGE_ORDER:
        if stage in matches:
            highest_stage = stage
            stage_score = STAGE_WEIGHT[stage]

    meta_score, meta_reason = score_caller_metadata(payload.caller_number, payload.claimed_authority)

    duration_flag = None
    if payload.call_duration_minutes and payload.call_duration_minutes > 45:
        duration_flag = "Unusually long call duration — consistent with sustained psychological pressure tactics"

    total_score = min(100, stage_score + meta_score + (10 if duration_flag else 0))

    if total_score >= 70:
        verdict = "CRITICAL — Likely active digital arrest scam"
        action = "Alert MHA cybercrime cell immediately. Advise disconnect and independent verification."
    elif total_score >= 40:
        verdict = "HIGH RISK — Strong scam escalation signature"
        action = "Flag for immediate human review. Do not process any pending transfer."
    elif total_score >= 15:
        verdict = "MODERATE — Early pretext pattern detected"
        action = "Monitor. Advise caution if authority claims escalate further."
    else:
        verdict = "LOW — No significant scam pattern detected"
        action = "No action required."

    return {
        "risk_score": total_score,
        "verdict": verdict,
        "recommended_action": action,
        "highest_stage_reached": highest_stage,
        "highest_stage_label": STAGE_LABEL.get(highest_stage),
        "stage_matches": matches,
        "metadata_flag": meta_reason,
        "duration_flag": duration_flag,
        "detected_before_payment": highest_stage != "PAYMENT_DEMAND",
    }


@router.post("/scam/analyze")
def analyze_transcript(payload: TranscriptInput):
    return analyze(payload)


@router.get("/scam/demo-cases")
def get_demo_cases():
    return {
        "cases": [
            {
                "id": "demo_1",
                "label": "Stage 1 — Courier pretext only",
                "transcript": "Sir your parcel containing illegal items has been detained by customs department. This is a serious case.",
                "caller_number": "9876543210",
                "claimed_authority": "Customs Department",
                "call_duration_minutes": 8,
            },
            {
                "id": "demo_2",
                "label": "Stage 3 — Isolation pressure active",
                "transcript": "This is CBI, a case has been registered against you. Do not disconnect this call and do not tell your family. You are under digital arrest and being monitored.",
                "caller_number": "9123456780",
                "claimed_authority": "CBI",
                "call_duration_minutes": 52,
            },
            {
                "id": "demo_3",
                "label": "Stage 4 — Payment demand, near-victimization",
                "transcript": "To prove your innocence you must transfer the amount to this government escrow account immediately as a refundable deposit.",
                "caller_number": "9988776655",
                "claimed_authority": "Enforcement Directorate",
                "call_duration_minutes": 78,
            },
        ]
    }

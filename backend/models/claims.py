"""
Claim models (PROJECT.md Sections 7, 8).

Imports nothing from backend/: the verifier depends on this module and must stay
drug-agnostic.
"""

from typing import Literal

from pydantic import BaseModel

ClaimSetStatus = Literal["ANSWERED", "PARTIAL", "INSUFFICIENT_EVIDENCE"]


class Claim(BaseModel):
    text: str
    evidence_id: str
    quote: str  # 5-30 words verbatim from that passage (verifier L1 checks it)


class ClaimSet(BaseModel):
    status: ClaimSetStatus
    claims: list[Claim]
    gaps: list[str]


Verdict = Literal["KEPT", "CUT_QUOTE", "CUT_SUPPORT", "CUT_DIRECTIVE", "CUT_BAD_ID"]


class VerifiedClaim(Claim):
    verdict: Verdict
    reason: str


class VerifiedClaimSet(BaseModel):
    kept: list[VerifiedClaim]
    cut: list[VerifiedClaim]
    claims_total: int
    claims_kept: int
    # Provider that produced the L2 results; None when no claim reached L2 or
    # both providers failed (remaining claims cut "verifier unavailable").
    verifier_provider: Literal["gemini", "groq"] | None

"""
Claim models (PROJECT.md Sections 7, 8).

Imports nothing from backend/: the verifier depends on this module and must stay
drug-agnostic. VerifiedClaim and VerifiedClaimSet are added with the verifier (CP4).
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

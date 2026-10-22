from typing import Literal

from backend.models.base import BaseSchema
from backend.models.enums import InvestigateStatus, SafetyCategory
from backend.models.evidence import EvidenceItem


class Redirect(BaseSchema):
    to: str  # "prescription_check"
    drugs: list[str]


class EarlyOutcome(BaseSchema):
    """
    A v2 /investigate status decided before retrieval (PROJECT.md Section 10):
    BLOCKED, UNAVAILABLE, NO_DRUG, NOT_RECOGNIZED, ONE_AT_A_TIME, REDIRECT.
    """

    status: InvestigateStatus
    message: str | None = None
    block_type: SafetyCategory | None = None
    redirect: Redirect | None = None


# --- v2 /investigate response (PROJECT.md Section 10) ---

class LabelRef(BaseSchema):
    title: str
    set_id: str
    effective_date: str | None
    url: str


class ResolvedDrugOut(BaseSchema):
    input_name: str
    rxcui: str | None
    preferred_name: str
    ingredients: list[str]
    label: LabelRef | None


class ResponseClaim(BaseSchema):
    text: str
    section: str  # copied from the cited evidence item
    evidence_id: str
    quote: str


class ResponseMeta(BaseSchema):
    latency_ms: int
    llm_calls: int
    verifier_provider: Literal["gemini", "groq"] | None
    cache_hit: bool
    verified: bool  # False until the verifier (CP4) checks the claims
    synthesizer_provider: Literal["gemini", "groq"] | None


class InvestigateResponse(BaseSchema):
    version: Literal["v2"] = "v2"
    status: InvestigateStatus
    message: str | None = None
    block_type: SafetyCategory | None = None
    redirect: Redirect | None = None
    intent: str | None = None
    drug: ResolvedDrugOut | None = None
    claims: list[ResponseClaim] = []
    claims_total: int = 0
    claims_kept: int = 0
    gaps: list[str] = []
    evidence: dict[str, EvidenceItem] = {}  # only items cited by kept claims
    meta: ResponseMeta

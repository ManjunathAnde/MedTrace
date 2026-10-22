from typing import Literal

from backend.models.base import BaseSchema
from backend.models.enums import InvestigateStatus, PrescriptionCheckStatus, SafetyCategory
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


# --- v2 /prescription-check response (PROJECT.md Section 10) ---

class ResolutionOut(BaseSchema):
    input_name: str
    status: Literal["RESOLVED", "NOT_RECOGNIZED"]
    rxcui: str | None = None
    preferred_name: str | None = None
    ingredients: list[str] = []
    label: LabelRef | None = None
    message: str | None = None  # NOT_RECOGNIZED only


class InteractionCard(BaseSchema):
    pair: tuple[str, str]
    finding: Literal["INTERACTION_DOCUMENTED", "NO_INTERACTION_STATED"]
    severity: Literal["High", "Moderate", "Info"]
    severity_rule: str
    claims: list[ResponseClaim]


class NeedsReview(BaseSchema):
    pair: tuple[str, str]
    evidence_ids: list[str]


class RecallRef(BaseSchema):
    ingredient: str
    evidence_id: str


class PrescriptionCheckMeta(BaseSchema):
    latency_ms: int
    llm_calls: int
    pairs_checked: int
    pairs_with_candidates: int
    verifier_provider: Literal["gemini", "groq"] | None
    cache_hit: bool
    verified: bool  # True once claims have been through the verifier


class PrescriptionCheckResponse(BaseSchema):
    version: Literal["v2"] = "v2"
    status: PrescriptionCheckStatus
    message: str | None = None
    resolution: list[ResolutionOut] = []
    interactions: list[InteractionCard] = []  # sorted High, Moderate, Info
    needs_review: list[NeedsReview] = []
    no_documented_interaction: list[tuple[str, str]] = []
    recalls: list[RecallRef] = []
    evidence: dict[str, EvidenceItem] = {}  # every item referenced
    footer: str = "Class-level interactions were not checked."
    meta: PrescriptionCheckMeta

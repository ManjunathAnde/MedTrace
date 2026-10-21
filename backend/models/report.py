from pydantic import Field

from backend.models.base import BaseSchema
from backend.models.enums import InvestigateStatus, ProfileType, SafetyCategory


class MedicationReport(BaseSchema):
    profile_used: ProfileType
    drug_name: str
    summary: str
    key_findings: list[str]
    warnings: list[str]
    contraindications: list[str]
    recalls: list[str]
    adverse_events: list[str]
    interactions: list[str]
    limitations: list[str]
    sources_used: list[str]
    completeness_score: float = Field(ge=0.0, le=1.0)


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

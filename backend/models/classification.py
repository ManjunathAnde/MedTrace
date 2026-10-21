from backend.models.base import BaseSchema
from backend.models.enums import (
    ProfileType,
    SafetyCategory,
    SafetyClassifierType,
    SafetyDecision,
    Wall1Action,
)


class LLMCallDiagnostics(BaseSchema):
    model: str
    duration_ms: float
    fallback_used: bool
    fallback_reason: str | None
    api_error_type: str | None
    validation_error: bool
    attempts: int = 1


class IntentClassificationResult(BaseSchema):
    profile: ProfileType
    confidence: float
    reason: str
    diagnostics: LLMCallDiagnostics | None = None


class SafetyClassificationResult(BaseSchema):
    decision: SafetyDecision
    reason: str
    classifier: SafetyClassifierType
    diagnostics: LLMCallDiagnostics | None = None


class Wall1Result(BaseSchema):
    """Safety wall 1 (rules). Rules only block or escalate, never clear."""

    action: Wall1Action
    category: SafetyCategory | None  # set when action is BLOCK
    matched: str | None  # the phrase that fired


class SafetyVerdict(BaseSchema):
    """Safety wall 2 (LLM) output schema, PROJECT.md Section 12.1."""

    safety: SafetyCategory
    safety_reason: str


class ExtractedDrugs(BaseSchema):
    """Extractor output schema, PROJECT.md Section 12.2: names exactly as typed."""

    drugs: list[str]

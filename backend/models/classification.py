from backend.models.base import BaseSchema
from backend.models.enums import ProfileType, SafetyClassifierType, SafetyDecision


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

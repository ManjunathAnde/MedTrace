from backend.models.base import BaseSchema
from backend.models.enums import ProfileType, SafetyClassifierType, SafetyDecision


class IntentClassificationResult(BaseSchema):
    profile: ProfileType
    confidence: float
    reason: str


class SafetyClassificationResult(BaseSchema):
    decision: SafetyDecision
    reason: str
    classifier: SafetyClassifierType

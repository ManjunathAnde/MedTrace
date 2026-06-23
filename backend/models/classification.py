from backend.models.base import BaseSchema
from backend.models.enums import ProfileType


class IntentClassificationResult(BaseSchema):
    profile: ProfileType
    confidence: float

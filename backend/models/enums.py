from enum import Enum


class ProfileType(str, Enum):
    FULL_INVESTIGATION = "full_investigation"
    WARNINGS_REVIEW = "warnings_review"
    CONTRAINDICATIONS_REVIEW = "contraindications_review"
    RECALL_INVESTIGATION = "recall_investigation"
    INTERACTION_INVESTIGATION = "interaction_investigation"
    ADVERSE_EVENT_INVESTIGATION = "adverse_event_investigation"


class InteractionSeverity(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"


# All unrecognized FDA recall classification values map to UNKNOWN
class RecallClassification(str, Enum):
    CLASS_I = "Class I"
    CLASS_II = "Class II"
    CLASS_III = "Class III"
    UNKNOWN = "unknown"


class SafetyDecision(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"


class SafetyClassifierType(str, Enum):
    RULE = "rule"
    GEMINI = "gemini"

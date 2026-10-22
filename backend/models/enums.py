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


# --- v2 (PROJECT.md Sections 5 and 10) ---

class SafetyCategory(str, Enum):
    """Wall 2 output; PERSONAL_ADVICE and SELF_HARM_RISK double as block_type."""

    SAFE = "SAFE"
    PERSONAL_ADVICE = "PERSONAL_ADVICE"
    SELF_HARM_RISK = "SELF_HARM_RISK"


class Wall1Action(str, Enum):
    BLOCK = "block"
    ESCALATE = "escalate"  # logged only; wall 2 behaves the same either way
    PASS = "pass"


class InvestigateStatus(str, Enum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"
    NO_DRUG = "NO_DRUG"
    NOT_RECOGNIZED = "NOT_RECOGNIZED"
    ONE_AT_A_TIME = "ONE_AT_A_TIME"
    REDIRECT = "REDIRECT"


class PrescriptionCheckStatus(str, Enum):
    COMPLETE = "COMPLETE"
    TOO_FEW = "TOO_FEW"
    TOO_MANY = "TOO_MANY"

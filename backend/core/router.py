"""
Profile router — maps IntentClassificationResult to a ProfileType.

Centralizes the low-confidence fallback policy so main.py contains no routing logic.
"""

import logging

from backend.llm.intent_classifier import LOW_CONFIDENCE_THRESHOLD
from backend.models.classification import IntentClassificationResult
from backend.models.enums import InvestigateStatus, ProfileType, SafetyCategory
from backend.models.report import EarlyOutcome, Redirect

logger = logging.getLogger(__name__)


def resolve_profile(intent: IntentClassificationResult) -> ProfileType:
    if intent.confidence < LOW_CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low confidence intent classification (%.2f) for profile '%s' — "
            "overriding to full_investigation",
            intent.confidence,
            intent.profile.value,
        )
        return ProfileType.FULL_INVESTIGATION
    return intent.profile


# --- v2 early outcomes (PROJECT.md Sections 5.1-5.3, 10) ---
# Statuses decided before retrieval. Messages are exact (spec text).

PERSONAL_ADVICE_MESSAGE = (
    "MedTrace provides FDA drug label information, not personal medical advice. "
    "Please talk to a pharmacist or doctor about your specific situation."
)
SELF_HARM_MESSAGE = (
    "It sounds like you might be going through something difficult. You don't have to "
    "handle it alone. You can call or text 988 to reach the Suicide & Crisis Lifeline, "
    "any time. If you're in immediate danger, call 911."
)
UNAVAILABLE_MESSAGE = "MedTrace couldn't complete its checks right now. Please try again."
NO_DRUG_MESSAGE = "Please include the medication name in your question."
ONE_AT_A_TIME_MESSAGE = (
    "Please ask about one medication at a time, or use Prescription Check to review "
    "several together."
)
NOT_RECOGNIZED_MESSAGE = "'{name}' wasn't recognized. Check the spelling and try again."

_BLOCK_MESSAGES = {
    SafetyCategory.PERSONAL_ADVICE: PERSONAL_ADVICE_MESSAGE,
    SafetyCategory.SELF_HARM_RISK: SELF_HARM_MESSAGE,
}


def blocked_outcome(category: SafetyCategory) -> EarlyOutcome:
    """Wall 1 block or wall 2 non-SAFE verdict -> BLOCKED with its exact message."""
    if category not in _BLOCK_MESSAGES:
        raise ValueError(f"not a block category: {category}")
    return EarlyOutcome(
        status=InvestigateStatus.BLOCKED,
        message=_BLOCK_MESSAGES[category],
        block_type=category,
    )


def unavailable_outcome() -> EarlyOutcome:
    """Safety check or extraction failed on both providers. Never BLOCKED."""
    return EarlyOutcome(status=InvestigateStatus.UNAVAILABLE, message=UNAVAILABLE_MESSAGE)


def not_recognized_outcome(name: str) -> EarlyOutcome:
    """RxNorm exact lookup missed (HTTP 200, not an error)."""
    return EarlyOutcome(
        status=InvestigateStatus.NOT_RECOGNIZED,
        message=NOT_RECOGNIZED_MESSAGE.format(name=name),
    )


def drug_count_outcome(drugs: list[str], profile: ProfileType) -> EarlyOutcome | None:
    """
    Section 5.2 drug count rules. None means exactly one drug: continue.
      0           -> NO_DRUG
      2+ interact -> REDIRECT to Prescription Check with the names
      2+ other    -> ONE_AT_A_TIME
    """
    if not drugs:
        return EarlyOutcome(status=InvestigateStatus.NO_DRUG, message=NO_DRUG_MESSAGE)
    if len(drugs) == 1:
        return None
    if profile == ProfileType.INTERACTION_INVESTIGATION:
        return EarlyOutcome(
            status=InvestigateStatus.REDIRECT,
            redirect=Redirect(to="prescription_check", drugs=list(drugs)),
        )
    return EarlyOutcome(status=InvestigateStatus.ONE_AT_A_TIME, message=ONE_AT_A_TIME_MESSAGE)

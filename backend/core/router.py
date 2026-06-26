"""
Profile router — maps IntentClassificationResult to a ProfileType.

Centralizes the low-confidence fallback policy so main.py contains no routing logic.
"""

import logging

from backend.llm.intent_classifier import LOW_CONFIDENCE_THRESHOLD
from backend.models.classification import IntentClassificationResult
from backend.models.enums import ProfileType

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

from backend.models.enums import ProfileType
from backend.profiles._base import RetrievalProfile
from backend.profiles import (
    adverse_event_investigation,
    contraindications_review,
    full_investigation,
    interaction_investigation,
    recall_investigation,
    warnings_review,
)

PROFILES: dict[ProfileType, RetrievalProfile] = {
    ProfileType.FULL_INVESTIGATION: full_investigation.run,
    ProfileType.WARNINGS_REVIEW: warnings_review.run,
    ProfileType.CONTRAINDICATIONS_REVIEW: contraindications_review.run,
    ProfileType.RECALL_INVESTIGATION: recall_investigation.run,
    ProfileType.INTERACTION_INVESTIGATION: interaction_investigation.run,
    ProfileType.ADVERSE_EVENT_INVESTIGATION: adverse_event_investigation.run,
}

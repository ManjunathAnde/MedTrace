"""
Contraindications Review profile — RxNorm → DailyMed.
"""

from backend.apis.rxnorm import fetch_drug_identity
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.profiles._base import _build_metadata, _call_dailymed


async def run(medication_name: str) -> MedicationEvidence:
    """
    Contracts:
      - Success        -> returns MedicationEvidence with label_evidence populated
      - RxNorm failure -> raises RxNormError (caller handles)

    Gemini reads label_evidence.contraindications.
    sources_attempted is always 1 for this profile.
    """
    identity = await fetch_drug_identity(medication_name)

    successful: list[str] = []
    failed: list[str] = []

    label = await _call_dailymed(identity.rxcui, successful, failed)

    return MedicationEvidence(
        profile_used=ProfileType.CONTRAINDICATIONS_REVIEW,
        drug_identity=identity,
        label_evidence=label,
        recall_evidence=None,
        adverse_event_evidence=None,
        interaction_evidence=None,
        metadata=_build_metadata(successful, failed),
    )

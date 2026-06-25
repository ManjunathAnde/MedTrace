"""
Full Investigation profile — RxNorm → DailyMed + FDA Recall + OpenFDA (concurrent).
"""

from backend.apis.rxnorm import fetch_drug_identity
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.profiles._base import _build_metadata, _gather_full_investigation


async def run(medication_name: str) -> MedicationEvidence:
    """
    Contracts:
      - Success        -> returns MedicationEvidence (completeness_score may be < 1.0)
      - RxNorm failure -> raises RxNormError (caller handles)

    DailyMed, FDA Recall, and OpenFDA are run concurrently after RxNorm resolves
    the drug identity. sources_attempted is always 3 for this profile.
    """
    identity = await fetch_drug_identity(medication_name)
    search_name = identity.generic_name or identity.normalized_name

    successful: list[str] = []
    failed: list[str] = []

    label, recall, aes = await _gather_full_investigation(
        identity.rxcui, search_name, successful, failed
    )

    return MedicationEvidence(
        profile_used=ProfileType.FULL_INVESTIGATION,
        drug_identity=identity,
        label_evidence=label,
        recall_evidence=recall,
        adverse_event_evidence=aes,
        interaction_evidence=None,
        metadata=_build_metadata(successful, failed),
    )

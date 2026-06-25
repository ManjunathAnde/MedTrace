"""
Recall Investigation profile — RxNorm → FDA Recall.
"""

from backend.apis.rxnorm import fetch_drug_identity
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.profiles._base import _build_metadata, _call_fda_recall


async def run(medication_name: str) -> MedicationEvidence:
    """
    Contracts:
      - Success          -> returns MedicationEvidence with recall_evidence populated
      - No recalls found -> recall_evidence.recalls == [], completeness_score == 1.0
      - RxNorm failure   -> raises RxNormError (caller handles)

    Zero recalls is not a failure. The FDA Recall client returns an empty RecallEvidence
    for HTTP 404 responses; only a network or HTTP error reduces completeness_score.
    sources_attempted is always 1 for this profile.
    """
    identity = await fetch_drug_identity(medication_name)
    search_name = identity.generic_name or identity.normalized_name

    successful: list[str] = []
    failed: list[str] = []

    recall = await _call_fda_recall(search_name, successful, failed)

    return MedicationEvidence(
        profile_used=ProfileType.RECALL_INVESTIGATION,
        drug_identity=identity,
        label_evidence=None,
        recall_evidence=recall,
        adverse_event_evidence=None,
        interaction_evidence=None,
        metadata=_build_metadata(successful, failed),
    )

"""
Adverse Event Investigation profile — RxNorm → OpenFDA.
"""

from backend.apis.rxnorm import fetch_drug_identity
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.profiles._base import _build_metadata, _call_openfda


async def run(medication_name: str) -> MedicationEvidence:
    """
    Contracts:
      - Success          -> returns MedicationEvidence with adverse_event_evidence populated
      - No events found  -> adverse_event_evidence.events == [], completeness_score == 1.0
      - RxNorm failure   -> raises RxNormError (caller handles)

    Zero adverse events is not a failure. The OpenFDA client returns an empty
    AdverseEventEvidence for HTTP 404 responses; only a network or HTTP error
    reduces completeness_score.
    sources_attempted is always 1 for this profile.
    """
    identity = await fetch_drug_identity(medication_name)
    search_name = identity.generic_name or identity.normalized_name

    successful: list[str] = []
    failed: list[str] = []

    aes = await _call_openfda(search_name, successful, failed)

    return MedicationEvidence(
        profile_used=ProfileType.ADVERSE_EVENT_INVESTIGATION,
        drug_identity=identity,
        label_evidence=None,
        recall_evidence=None,
        adverse_event_evidence=aes,
        interaction_evidence=None,
        metadata=_build_metadata(successful, failed),
    )

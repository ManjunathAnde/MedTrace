"""
Shared orchestration utilities for all retrieval profiles.

Each per-API helper handles success/failure tracking so profile files
contain no error-handling boilerplate. _gather_full_investigation runs
the three Full Investigation sources concurrently to reduce wall time.
"""

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from backend.apis.dailymed import DailyMedError, fetch_label_evidence
from backend.apis.fda_recall import FDARecallServiceError, fetch_recall_evidence
from backend.apis.openfda import OpenFDAServiceError, fetch_adverse_event_evidence
from backend.models.evidence import (
    AdverseEventEvidence,
    EvidenceMetadata,
    LabelEvidence,
    MedicationEvidence,
    RecallEvidence,
)


class RetrievalProfile(Protocol):
    async def __call__(self, medication_name: str) -> MedicationEvidence: ...


def _build_metadata(
    successful_sources: list[str],
    failed_sources: list[str],
) -> EvidenceMetadata:
    attempted = len(successful_sources) + len(failed_sources)
    succeeded = len(successful_sources)
    return EvidenceMetadata(
        sources_attempted=attempted,
        sources_succeeded=succeeded,
        sources_failed=len(failed_sources),
        successful_sources=successful_sources,
        failed_sources=failed_sources,
        completeness_score=succeeded / attempted if attempted > 0 else 0.0,
        retrieved_at=datetime.now(timezone.utc),
    )


async def _call_dailymed(
    rxcui: str | None,
    successful: list[str],
    failed: list[str],
) -> LabelEvidence | None:
    # rxcui=None means RxNorm resolved the drug but not to a specific concept —
    # DailyMed cannot be called without a valid rxcui, so treat as failed.
    if rxcui is None:
        failed.append("DailyMed")
        return None
    try:
        result = await fetch_label_evidence(rxcui)
        successful.append("DailyMed")
        return result
    except DailyMedError:
        failed.append("DailyMed")
        return None


async def _call_fda_recall(
    search_name: str,
    successful: list[str],
    failed: list[str],
) -> RecallEvidence | None:
    # HTTP 404 (no recalls) is handled inside the client as RecallEvidence(recalls=[]).
    # Only FDARecallServiceError (network/HTTP failure) is a true failure.
    try:
        result = await fetch_recall_evidence(search_name)
        successful.append("FDA Recall")
        return result
    except FDARecallServiceError:
        failed.append("FDA Recall")
        return None


async def _call_openfda(
    search_name: str,
    successful: list[str],
    failed: list[str],
) -> AdverseEventEvidence | None:
    # HTTP 404 (no events) is handled inside the client as AdverseEventEvidence(events=[]).
    # Only OpenFDAServiceError (network/HTTP failure) is a true failure.
    try:
        result = await fetch_adverse_event_evidence(search_name)
        successful.append("OpenFDA")
        return result
    except OpenFDAServiceError:
        failed.append("OpenFDA")
        return None


async def _gather_full_investigation(
    rxcui: str | None,
    search_name: str,
    successful: list[str],
    failed: list[str],
) -> tuple[LabelEvidence | None, RecallEvidence | None, AdverseEventEvidence | None]:
    """
    Run DailyMed, FDA Recall, and OpenFDA concurrently.

    The three sources have no data dependency on each other — all require
    only the resolved identity from RxNorm. Running concurrently reduces
    Full Investigation wall time from additive (DailyMed + FDA Recall + OpenFDA)
    to max(DailyMed, FDA Recall, OpenFDA).
    """
    return await asyncio.gather(
        _call_dailymed(rxcui, successful, failed),
        _call_fda_recall(search_name, successful, failed),
        _call_openfda(search_name, successful, failed),
    )

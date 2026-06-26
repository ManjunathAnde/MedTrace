"""
Shared orchestration utilities for all retrieval profiles.

Each per-API helper handles success/failure tracking so profile files
contain no error-handling boilerplate. _gather_full_investigation runs
the three Full Investigation sources concurrently; source lists are
assembled in canonical order after all tasks complete so metadata is
identical across repeated executions with the same inputs.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

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

# Type alias for the uniform public interface of all retrieval profiles.
RetrievalProfile = Callable[[str], Awaitable[MedicationEvidence]]


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


# --- Private safe-fetch helpers ---
# Return the evidence object on success, None on any failure.
# No source-list side effects — safe to use inside asyncio.gather.

async def _fetch_label_safe(rxcui: str | None) -> LabelEvidence | None:
    # rxcui=None means RxNorm resolved the drug but not to a specific concept;
    # DailyMed cannot be called without a valid rxcui.
    if rxcui is None:
        return None
    try:
        return await fetch_label_evidence(rxcui)
    except DailyMedError:
        return None


async def _fetch_recall_safe(search_name: str) -> RecallEvidence | None:
    # HTTP 404 (no recalls) is handled inside the client as RecallEvidence(recalls=[]).
    # Only FDARecallServiceError (network/HTTP failure) produces None here.
    try:
        return await fetch_recall_evidence(search_name)
    except FDARecallServiceError:
        return None


async def _fetch_adverse_safe(search_name: str) -> AdverseEventEvidence | None:
    # HTTP 404 (no events) is handled inside the client as AdverseEventEvidence(events=[]).
    # Only OpenFDAServiceError (network/HTTP failure) produces None here.
    try:
        return await fetch_adverse_event_evidence(search_name)
    except OpenFDAServiceError:
        return None


# --- Public call helpers ---
# Used by single-source profiles. Delegate to the safe-fetch helpers and
# record the outcome in the caller's source-tracking lists.

async def _call_dailymed(
    rxcui: str | None,
    successful: list[str],
    failed: list[str],
) -> LabelEvidence | None:
    result = await _fetch_label_safe(rxcui)
    (successful if result is not None else failed).append("DailyMed")
    return result


async def _call_fda_recall(
    search_name: str,
    successful: list[str],
    failed: list[str],
) -> RecallEvidence | None:
    result = await _fetch_recall_safe(search_name)
    (successful if result is not None else failed).append("FDA Recall")
    return result


async def _call_openfda(
    search_name: str,
    successful: list[str],
    failed: list[str],
) -> AdverseEventEvidence | None:
    result = await _fetch_adverse_safe(search_name)
    (successful if result is not None else failed).append("OpenFDA")
    return result


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

    Source lists are populated in canonical order (DailyMed, FDA Recall, OpenFDA)
    after all tasks complete. This decouples metadata ordering from asyncio.gather
    completion order so results are deterministic across executions.
    """
    label, recall, aes = await asyncio.gather(
        _fetch_label_safe(rxcui),
        _fetch_recall_safe(search_name),
        _fetch_adverse_safe(search_name),
    )

    # Canonical order: DailyMed, FDA Recall, OpenFDA — always, regardless of which
    # task completed first.
    for name, result in (
        ("DailyMed", label),
        ("FDA Recall", recall),
        ("OpenFDA", aes),
    ):
        (successful if result is not None else failed).append(name)

    return label, recall, aes

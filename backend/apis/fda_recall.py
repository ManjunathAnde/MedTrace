"""
FDA Recall API client — drug recall evidence.
All external API clients in this project are async. No synchronous clients are used.
"""
from datetime import datetime

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.enums import RecallClassification
from backend.models.evidence import RecallEvidence, RecallRecord

_BASE_URL = "https://api.fda.gov/drug/enforcement.json"
_cache: TTLCache = TTLCache(maxsize=100, ttl=86400)

# FDA enforcement classification strings mapped to enum values.
# Any unrecognized string maps to UNKNOWN — never crash on unexpected values.
_CLASSIFICATION_MAP: dict[str, RecallClassification] = {
    "Class I": RecallClassification.CLASS_I,
    "Class II": RecallClassification.CLASS_II,
    "Class III": RecallClassification.CLASS_III,
}


class FDARecallError(Exception):
    pass


class FDARecallNotFoundError(FDARecallError):
    pass


class FDARecallServiceError(FDARecallError):
    pass


def _parse_recall_date(date_str: str | None) -> datetime | None:
    # FDA enforcement dates use YYYYMMDD format, not ISO 8601.
    # Parse failures return None rather than crashing.
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d")
    except (ValueError, TypeError):
        return None


def _map_classification(raw: str | None) -> RecallClassification:
    if not raw:
        return RecallClassification.UNKNOWN
    return _CLASSIFICATION_MAP.get(raw, RecallClassification.UNKNOWN)


def _normalize_record(raw: dict) -> RecallRecord:
    return RecallRecord(
        recall_number=raw.get("recall_number", ""),
        reason=raw.get("reason_for_recall", ""),
        classification=_map_classification(raw.get("classification")),
        recall_date=_parse_recall_date(raw.get("recall_initiation_date")),
        status=raw.get("status", ""),
    )


async def fetch_recall_evidence(generic_name: str) -> RecallEvidence:
    """
    Fetch recall evidence for a drug by generic name.

    Searches the OpenFDA drug enforcement endpoint by product_description.
    Recalls are returned sorted newest-first by recall_initiation_date;
    records with unparseable dates are placed at the end.

    Contracts:
      - Success          -> returns RecallEvidence (recalls list may be empty)
      - No recalls found -> returns RecallEvidence(recalls=[], total_count=0)
      - Service failure  -> raises FDARecallServiceError

    Note: Zero recalls is valid information, not an error condition.
    OpenFDA recall searches return HTTP 404 when no recall records match
    the query. This is treated as a successful retrieval with zero recalls,
    not a service failure.
    """
    cache_key = hashkey(generic_name.strip().lower())

    if cache_key in _cache:
        return _cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Search by product_description rather than openfda.generic_name.
            # openfda.* annotations are sparsely populated in enforcement records —
            # many recalls are never FDA-annotated and have no openfda block at all.
            # product_description is always present (manufacturer-submitted) and
            # ensures maximum recall coverage at the cost of occasional false positives.
            response = await client.get(
                _BASE_URL,
                params={
                    "search": f'product_description:"{generic_name}"',
                    "limit": 100,
                },
            )
    except httpx.RequestError as exc:
        raise FDARecallServiceError(f"FDA recall request failed: {exc}") from exc

    # OpenFDA returns 404 when no enforcement records match the query.
    # This is an expected response meaning zero recalls — not a service error.
    if response.status_code == 404:
        evidence = RecallEvidence(recalls=[], total_count=0)
        _cache[cache_key] = evidence
        return evidence

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FDARecallServiceError(
            f"FDA recall endpoint returned HTTP {exc.response.status_code}"
        ) from exc

    body = response.json()
    raw_results = body.get("results", [])
    total_count = (
        body.get("meta", {}).get("results", {}).get("total", len(raw_results))
    )

    recalls = [_normalize_record(r) for r in raw_results]
    # Sort newest-first so recalls[0] is always the most recent.
    # Records with unparseable dates (recall_date=None) sort to the end via datetime.min.
    recalls.sort(key=lambda r: r.recall_date or datetime.min, reverse=True)
    evidence = RecallEvidence(recalls=recalls, total_count=total_count)
    _cache[cache_key] = evidence
    return evidence

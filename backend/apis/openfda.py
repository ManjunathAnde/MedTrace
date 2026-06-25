"""
OpenFDA adverse event API client — drug adverse event evidence.
All external API clients in this project are async. No synchronous clients are used.

Known limitation: OpenFDA caps results at 100 per call. Drugs with
large adverse event histories may have truncated results. Pagination
not implemented in V1.
Returns top MAX_ADVERSE_EVENTS reaction terms by frequency.
Truncated intentionally at this limit.

Implementation note on total_count:
  The OpenFDA count aggregation endpoint (used to retrieve ranked reaction terms)
  does not include a meta.results.total field. Total report count is retrieved
  via a separate lightweight query (limit=1) run in parallel. This adds no
  latency because all three sub-calls (terms, total, serious) use asyncio.gather.
"""

import asyncio

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.evidence import AdverseEvent, AdverseEventEvidence

_BASE_URL = "https://api.fda.gov/drug/event.json"
_cache: TTLCache = TTLCache(maxsize=100, ttl=86400)

MAX_ADVERSE_EVENTS = 100


class OpenFDAError(Exception):
    pass


class OpenFDANotFoundError(OpenFDAError):
    """
    Defined for interface consistency with other API clients.
    Not raised by fetch_adverse_event_evidence — zero events is valid data, not an
    exceptional condition. OpenFDA returns HTTP 404 when no adverse event records
    match the query; this is handled by returning an empty AdverseEventEvidence.
    """


class OpenFDAServiceError(OpenFDAError):
    pass


async def _count_reactions(
    client: httpx.AsyncClient, search: str
) -> list[dict]:
    """
    Fetch reaction term counts using OpenFDA count aggregation.

    Returns list of {term, count} dicts sorted by count descending (OpenFDA default).
    Returns [] on 404 — no records found is not an error.
    Raises OpenFDAServiceError on HTTP or network failure.
    """
    try:
        response = await client.get(
            _BASE_URL,
            params={
                "search": search,
                "count": "patient.reaction.reactionmeddrapt.exact",
                "limit": MAX_ADVERSE_EVENTS,
            },
        )
    except httpx.RequestError as exc:
        raise OpenFDAServiceError(f"OpenFDA event request failed: {exc}") from exc

    if response.status_code == 404:
        return []

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenFDAServiceError(
            f"OpenFDA event endpoint returned HTTP {exc.response.status_code}"
        ) from exc

    return response.json().get("results", [])


async def _fetch_report_total(
    client: httpx.AsyncClient, search: str
) -> int:
    """
    Fetch the total number of adverse event reports for a drug.

    Uses a limit=1 regular search to read meta.results.total — the count
    aggregation endpoint does not include this field.
    Returns 0 on 404 or failure (total is informational, not critical).
    """
    try:
        response = await client.get(
            _BASE_URL,
            params={"search": search, "limit": 1},
        )
    except httpx.RequestError:
        return 0

    if response.status_code == 404:
        return 0

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return 0

    return response.json().get("meta", {}).get("results", {}).get("total", 0)


async def _fetch_serious_terms(
    client: httpx.AsyncClient, base_search: str
) -> set[str]:
    """
    Returns uppercase reaction terms that appear in reports marked serious:1.

    Never raises — serious classification is supplemental. Any failure returns
    an empty set so the main evidence collection is not blocked.
    """
    try:
        terms = await _count_reactions(client, f"{base_search} AND serious:1")
        return {item["term"].upper() for item in terms}
    except OpenFDAServiceError:
        return set()


async def fetch_adverse_event_evidence(generic_name: str) -> AdverseEventEvidence:
    """
    Fetch adverse event evidence for a drug by generic name.

    Uses OpenFDA count aggregation to retrieve the most frequently reported
    reaction terms. Three parallel sub-calls run within a single AsyncClient:
      1. All reaction term counts
      2. Total adverse event report count (separate call — count endpoint has no meta)
      3. Serious reaction terms (from reports marked serious:1)

    Events are sorted by count descending; most reported event is first.

    Contracts:
      - Success          -> returns AdverseEventEvidence (events list may be empty)
      - No events found  -> returns AdverseEventEvidence(events=[], total_count=0)
      - Service failure  -> raises OpenFDAServiceError

    Note: Zero events is valid information, not an error condition.
    OpenFDA returns HTTP 404 when no adverse event records match the query.
    This is treated as a successful retrieval with zero events, not a service failure.
    """
    cache_key = hashkey(generic_name.strip().lower())

    if cache_key in _cache:
        return _cache[cache_key]

    # Search by patient.drug.openfda.generic_name — FDA-annotated and standardized.
    # Preferred over patient.drug.medicinalproduct (raw reporter text with inconsistent
    # spellings) and openfda.substance_name (too narrow for multi-ingredient products).
    # openfda.generic_name aligns with the generic_name resolved by RxNorm and has
    # significantly better annotation coverage in FAERS than in enforcement records.
    base_search = f'patient.drug.openfda.generic_name:"{generic_name}"'

    async with httpx.AsyncClient(timeout=8.0) as client:
        raw_terms, total_count, serious_terms = await asyncio.gather(
            _count_reactions(client, base_search),
            _fetch_report_total(client, base_search),
            _fetch_serious_terms(client, base_search),
        )

    events = [
        AdverseEvent(
            term=item["term"].title(),
            count=item["count"],
            serious=item["term"].upper() in serious_terms,
        )
        for item in raw_terms
    ]
    # Sort most-reported first so events[0] is always the top signal.
    events.sort(key=lambda e: e.count, reverse=True)

    evidence = AdverseEventEvidence(events=events, total_count=total_count)
    _cache[cache_key] = evidence
    return evidence

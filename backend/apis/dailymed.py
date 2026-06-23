"""
DailyMed API client — drug label evidence.

All external API clients in this project are async. No synchronous clients are used.

Implementation note:
  The DailyMed v2 REST API provides label metadata (setid, version, title)
  but does not serve label text sections in JSON format. Label text is only
  available as a ZIP/XML download, which is not appropriate for this workflow.

  DailyMed and OpenFDA both serve the same FDA Structured Product Label (SPL)
  data. This client uses a two-step approach:
    Step 1 — DailyMed: resolve rxcui -> setid (canonical label identifier)
    Step 2 — OpenFDA drug/label: fetch structured label sections by set_id

  DailyMed remains the authoritative identity source. OpenFDA is used solely
  as the JSON delivery mechanism for the same underlying SPL text.
"""

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.evidence import LabelEvidence

_DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
_OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
_cache: TTLCache = TTLCache(maxsize=100, ttl=86400)


class DailyMedError(Exception):
    pass


class DailyMedNotFoundError(DailyMedError):
    pass


class DailyMedServiceError(DailyMedError):
    pass


async def _get_setid(client: httpx.AsyncClient, rxcui: str) -> str:
    try:
        response = await client.get(
            f"{_DAILYMED_URL}/spls.json",
            params={"rxcui": rxcui},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # DailyMed HTTP 500 with empty data[] observed for invalid rxcui inputs —
        # mapped to NotFoundError. This is documented API behaviour for malformed input.
        try:
            body = exc.response.json()
        except Exception:
            body = {}
        if exc.response.status_code == 500 and not body.get("data"):
            raise DailyMedNotFoundError(
                f"No label found in DailyMed for rxcui: '{rxcui}'"
            ) from exc
        raise DailyMedServiceError(
            f"DailyMed returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise DailyMedServiceError(f"DailyMed request failed: {exc}") from exc

    data = response.json().get("data", [])
    if not data:
        raise DailyMedNotFoundError(
            f"No label found in DailyMed for rxcui: '{rxcui}'"
        )

    # Use the most recently published label (DailyMed returns newest first)
    return data[0]["setid"]


async def _fetch_label_by_setid(client: httpx.AsyncClient, setid: str) -> dict:
    try:
        response = await client.get(
            _OPENFDA_LABEL_URL,
            params={"search": f'set_id:"{setid}"', "limit": 1},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise DailyMedServiceError(
            f"OpenFDA label endpoint returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise DailyMedServiceError(
            f"OpenFDA label endpoint request failed: {exc}"
        ) from exc

    results = response.json().get("results", [])
    if not results:
        raise DailyMedNotFoundError(
            f"No label sections found via OpenFDA for DailyMed setid: '{setid}'"
        )

    return results[0]


def _extract_text_list(label: dict, *field_names: str) -> list[str]:
    # Precautions/warnings field name varies across SPL format versions.
    # Check all known field names and return the first one present.
    for field in field_names:
        value = label.get(field)
        if value:
            return value if isinstance(value, list) else [value]
    return []


async def fetch_label_evidence(rxcui: str) -> LabelEvidence:
    """
    Fetch drug label evidence for a given RxCUI.

    Two-step process:
      Step 1 — DailyMed resolves rxcui to a canonical setid.
      Step 2 — OpenFDA label endpoint fetches structured section text by setid.
    Both sources serve identical FDA SPL data; DailyMed is the authoritative
    identity source.

    Contracts:
      - Success         -> returns LabelEvidence
      - Not found       -> raises DailyMedNotFoundError
      - Service failure -> raises DailyMedServiceError
    """
    cache_key = hashkey(rxcui)

    if cache_key in _cache:
        return _cache[cache_key]

    async with httpx.AsyncClient(timeout=8.0) as client:
        setid = await _get_setid(client, rxcui)
        label = await _fetch_label_by_setid(client, setid)

    evidence = LabelEvidence(
        boxed_warnings=_extract_text_list(label, "boxed_warning"),
        contraindications=_extract_text_list(label, "contraindications"),
        # Precautions field name varies by SPL format version — check all known keys
        precautions=_extract_text_list(
            label,
            "warnings_and_cautions",
            "warnings_and_precautions",
            "precautions",
        ),
    )

    _cache[cache_key] = evidence
    return evidence

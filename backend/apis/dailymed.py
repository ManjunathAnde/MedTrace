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

import logging
import re

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.evidence import LabelEvidence

logger = logging.getLogger(__name__)

_DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
_OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
_LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
_MAX_LABEL_ATTEMPTS = 10
_cache: TTLCache = TTLCache(maxsize=100, ttl=86400)


class DailyMedError(Exception):
    pass


class DailyMedNotFoundError(DailyMedError):
    pass


class DailyMedServiceError(DailyMedError):
    pass


def title_tier(title: str, typed_name: str, single_ingredient: bool) -> int:
    """
    PROJECT.md Section 5.4 tie-breakers, case-insensitive, whole-word:
      1. title starts with the typed name, names a single product, and is not
         a combination (" AND ") when the product has one ingredient
      2. title starts with the typed name
      3. typed name appears anywhere in the title
      4. none of the above (first SPL fallback)
    """
    word = rf"{re.escape(typed_name.strip())}\b"
    starts = re.match(word, title, re.IGNORECASE) is not None
    is_combination = " AND " in title.upper()
    # Multi-product SPLs list one "(ingredient)" group per product before "[labeler]".
    is_single_product = title.split("[")[0].count("(") <= 1
    if starts and is_single_product and not (single_ingredient and is_combination):
        return 1
    if starts:
        return 2
    if re.search(rf"\b{word}", title, re.IGNORECASE):
        return 3
    return 4


def order_spls(
    spls: list[dict], typed_name: str, single_ingredient: bool
) -> list[tuple[int, dict]]:
    """Stable sort by tier, so page order breaks ties within a tier."""
    tiers = [
        (title_tier(spl.get("title") or "", typed_name, single_ingredient), spl)
        for spl in spls
    ]
    return sorted(tiers, key=lambda t: t[0])


async def _get_spls(client: httpx.AsyncClient, rxcui: str) -> list[dict]:
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

    # First page only (DailyMed returns newest first)
    data = response.json().get("data", [])
    if not data:
        raise DailyMedNotFoundError(
            f"No label found in DailyMed for rxcui: '{rxcui}'"
        )
    return data


async def _fetch_label_by_setid(client: httpx.AsyncClient, setid: str) -> dict:
    try:
        response = await client.get(
            _OPENFDA_LABEL_URL,
            params={"search": f'set_id:"{setid}"', "limit": 1},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # OpenFDA answers 404 when no label matches the set_id
        if exc.response.status_code == 404:
            raise DailyMedNotFoundError(
                f"No label sections found via OpenFDA for DailyMed setid: '{setid}'"
            ) from exc
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


def _format_effective_time(value: str | None) -> str | None:
    # OpenFDA effective_time is YYYYMMDD
    if value and len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return None


async def fetch_label_evidence(
    rxcui: str, typed_name: str, single_ingredient: bool
) -> LabelEvidence:
    """
    Fetch drug label evidence for a given RxCUI.

    Two-step process:
      Step 1 — DailyMed lists SPLs for the rxcui (first page), ordered by the
               Section 5.4 tie-breakers against the typed name.
      Step 2 — OpenFDA label endpoint fetches structured section text by setid.
               A setid missing from OpenFDA is skipped (logged) and the next SPL
               is tried, up to _MAX_LABEL_ATTEMPTS.
    Both sources serve identical FDA SPL data; DailyMed is the authoritative
    identity source.

    Contracts:
      - Success         -> returns LabelEvidence
      - Not found       -> raises DailyMedNotFoundError
      - Service failure -> raises DailyMedServiceError
    """
    cache_key = hashkey(rxcui, typed_name.strip().lower(), single_ingredient)

    if cache_key in _cache:
        return _cache[cache_key]

    async with httpx.AsyncClient(timeout=8.0) as client:
        spls = await _get_spls(client, rxcui)
        skipped: list[str] = []
        for tier, spl in order_spls(spls, typed_name, single_ingredient)[:_MAX_LABEL_ATTEMPTS]:
            try:
                label = await _fetch_label_by_setid(client, spl["setid"])
            except DailyMedNotFoundError:
                logger.info(
                    "Label skip: setid %s not in OpenFDA (%s) for '%s'",
                    spl["setid"], spl.get("title"), typed_name,
                )
                skipped.append(spl["setid"])
                continue
            break
        else:
            logger.warning(
                "No OpenFDA label for '%s' (rxcui %s) after %d attempts",
                typed_name, rxcui, len(skipped),
            )
            raise DailyMedNotFoundError(
                f"No label sections found via OpenFDA for rxcui: '{rxcui}' "
                f"after {len(skipped)} attempts"
            )

    evidence = LabelEvidence(
        label_title=spl.get("title") or "",
        set_id=spl["setid"],
        effective_date=_format_effective_time(label.get("effective_time")),
        url=_LABEL_URL.format(setid=spl["setid"]),
        tie_breaker=tier,
        skipped_set_ids=skipped,
        boxed_warnings=_extract_text_list(label, "boxed_warning"),
        indications_and_usage=_extract_text_list(label, "indications_and_usage"),
        dosage_and_administration=_extract_text_list(label, "dosage_and_administration"),
        contraindications=_extract_text_list(label, "contraindications"),
        # Precautions field name varies by SPL format version — check all known keys
        precautions=_extract_text_list(
            label,
            "warnings_and_cautions",
            "warnings_and_precautions",
            "warnings",
            "precautions",
        ),
        drug_interactions=_extract_text_list(label, "drug_interactions"),
    )

    _cache[cache_key] = evidence
    return evidence

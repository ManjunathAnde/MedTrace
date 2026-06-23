"""
RxNorm API client — drug identity resolution.

All external API clients in this project are async. No synchronous clients are used.
"""

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.evidence import DrugIdentity

_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
_cache: TTLCache = TTLCache(maxsize=100, ttl=86400)


class RxNormError(Exception):
    pass


class RxNormDrugNotFoundError(RxNormError):
    pass


class RxNormServiceError(RxNormError):
    pass


async def _get_rxcui_candidates(
    client: httpx.AsyncClient, drug_name: str
) -> list[str]:
    try:
        response = await client.get(
            f"{_BASE_URL}/rxcui.json",
            params={"name": drug_name, "search": 1},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RxNormServiceError(
            f"RxNorm returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise RxNormServiceError(f"RxNorm request failed: {exc}") from exc

    return response.json().get("idGroup", {}).get("rxnormId") or []


async def _resolve_rxcui(
    client: httpx.AsyncClient, candidates: list[str]
) -> str:
    # Multi-match resolution:
    # Prefer exact ingredient (tty=IN) concept if present in results.
    # Fall back to first result if no exact ingredient match found.
    if len(candidates) == 1:
        return candidates[0]

    for rxcui in candidates:
        try:
            response = await client.get(f"{_BASE_URL}/rxcui/{rxcui}/properties.json")
            response.raise_for_status()
            if response.json().get("properties", {}).get("tty") == "IN":
                return rxcui
        except (httpx.HTTPStatusError, httpx.RequestError):
            continue

    return candidates[0]


async def _get_preferred_name(
    client: httpx.AsyncClient, rxcui: str
) -> str | None:
    try:
        response = await client.get(f"{_BASE_URL}/rxcui/{rxcui}/properties.json")
        response.raise_for_status()
        return response.json().get("properties", {}).get("name")
    except (httpx.HTTPStatusError, httpx.RequestError):
        return None


async def _get_related_names(
    client: httpx.AsyncClient, rxcui: str, tty: str
) -> list[str]:
    try:
        response = await client.get(
            f"{_BASE_URL}/rxcui/{rxcui}/related.json",
            params={"tty": tty},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RxNormServiceError(
            f"RxNorm returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise RxNormServiceError(f"RxNorm request failed: {exc}") from exc

    groups = response.json().get("relatedGroup", {}).get("conceptGroup", [])
    return [
        concept["name"]
        for group in groups
        for concept in group.get("conceptProperties", [])
        if concept.get("name")
    ]


async def fetch_drug_identity(drug_name: str) -> DrugIdentity:
    """
    Resolve a drug name to a DrugIdentity via RxNorm.

    Contracts:
      - Success        → returns DrugIdentity
      - Drug not found → raises RxNormDrugNotFoundError
      - Service failure → raises RxNormServiceError

    Field semantics:
      - input_name      = exactly what the user typed
      - normalized_name = canonical RxNorm preferred term for the resolved concept
    """
    cache_key = hashkey(drug_name.strip().lower())

    if cache_key in _cache:
        return _cache[cache_key]

    async with httpx.AsyncClient(timeout=8.0) as client:
        candidates = await _get_rxcui_candidates(client, drug_name.strip())

        if not candidates:
            raise RxNormDrugNotFoundError(
                f"Drug not recognized by RxNorm: '{drug_name}'"
            )

        rxcui = await _resolve_rxcui(client, candidates)

        # normalized_name = canonical RxNorm preferred term for this concept
        # input_name      = exactly what the user typed
        preferred_name = await _get_preferred_name(client, rxcui)
        normalized_name = preferred_name or drug_name.strip()

        ingredients = await _get_related_names(client, rxcui, "IN")

        # Brand names are supplemental — failure returns empty list, never raises
        try:
            brand_names = await _get_related_names(client, rxcui, "BN")
        except RxNormServiceError:
            brand_names = []

    identity = DrugIdentity(
        input_name=drug_name,
        normalized_name=normalized_name,
        generic_name=ingredients[0] if ingredients else None,  # canonical casing from RxNorm
        rxcui=rxcui,
        brand_names=brand_names,
    )

    _cache[cache_key] = identity
    return identity

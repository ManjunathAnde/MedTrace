"""
RxNorm API client — drug identity resolution.

All external API clients in this project are async. No synchronous clients are used.
"""

import asyncio
import logging

import httpx
from cachetools import TTLCache
from cachetools.keys import hashkey

from backend.models.evidence import DrugIdentity

logger = logging.getLogger(__name__)

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


def select_rxcui(
    input_name: str, candidates: list[tuple[str, str | None, str | None]]
) -> str:
    """
    Pick one rxcui from (rxcui, name, tty) candidates, in this order:
      1. RxNorm name equals the input (case-insensitive)
      2. first tty=IN
      3. first candidate
    name/tty are None when the properties call failed.
    """
    target = input_name.strip().lower()
    for rxcui, name, _ in candidates:
        if name is not None and name.strip().lower() == target:
            return rxcui
    for rxcui, _, tty in candidates:
        if tty == "IN":
            return rxcui
    return candidates[0][0]


async def _resolve_rxcui(
    client: httpx.AsyncClient, candidates: list[str], input_name: str
) -> str:
    if len(candidates) == 1:
        return candidates[0]

    described: list[tuple[str, str | None, str | None]] = []
    for rxcui in candidates:
        try:
            response = await client.get(f"{_BASE_URL}/rxcui/{rxcui}/properties.json")
            response.raise_for_status()
            properties = response.json().get("properties", {})
            described.append((rxcui, properties.get("name"), properties.get("tty")))
        except (httpx.HTTPStatusError, httpx.RequestError):
            described.append((rxcui, None, None))

    return select_rxcui(input_name, described)


async def _get_preferred_name(
    client: httpx.AsyncClient, rxcui: str
) -> str | None:
    try:
        response = await client.get(f"{_BASE_URL}/rxcui/{rxcui}/properties.json")
        response.raise_for_status()
        return response.json().get("properties", {}).get("name")
    except (httpx.HTTPStatusError, httpx.RequestError):
        return None


def filter_brands_by_ingredients(
    product_ingredients: set[str], brands: list[tuple[str, set[str] | None]]
) -> list[str]:
    """
    Keep brand names whose ingredient rxcui set equals the product's.
    Combination brands (e.g. Yosprala under omeprazole) are dropped.
    A brand whose ingredients could not be fetched (None) is dropped.
    """
    return [
        name for name, ingredients in brands
        if ingredients is not None and ingredients == product_ingredients
    ]


async def _get_related_concepts(
    client: httpx.AsyncClient, rxcui: str, tty: str
) -> list[tuple[str, str]]:
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
        (concept["rxcui"], concept["name"])
        for group in groups
        for concept in group.get("conceptProperties", [])
        if concept.get("rxcui") and concept.get("name")
    ]


async def _get_brand_ingredients(
    client: httpx.AsyncClient, brand_rxcui: str, brand_name: str
) -> set[str] | None:
    try:
        return {rxcui for rxcui, _ in await _get_related_concepts(client, brand_rxcui, "IN")}
    except RxNormServiceError as exc:
        logger.warning("RxNorm brand ingredients failed, brand dropped: %s (%s)", brand_name, exc)
        return None


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

        rxcui = await _resolve_rxcui(client, candidates, drug_name.strip())

        # normalized_name = canonical RxNorm preferred term for this concept
        # input_name      = exactly what the user typed
        preferred_name = await _get_preferred_name(client, rxcui)
        normalized_name = preferred_name or drug_name.strip()

        ingredient_concepts = await _get_related_concepts(client, rxcui, "IN")
        ingredients = [name for _, name in ingredient_concepts]

        # Brand names are supplemental — failure returns empty list, never raises.
        # Only brands with exactly the product's ingredients are kept.
        try:
            brand_concepts = await _get_related_concepts(client, rxcui, "BN")
        except RxNormServiceError:
            brand_concepts = []
        brand_ingredients = await asyncio.gather(
            *(_get_brand_ingredients(client, b_rxcui, b_name) for b_rxcui, b_name in brand_concepts)
        )
        brand_names = filter_brands_by_ingredients(
            {i_rxcui for i_rxcui, _ in ingredient_concepts},
            [(b_name, ings) for (_, b_name), ings in zip(brand_concepts, brand_ingredients)],
        )

    identity = DrugIdentity(
        input_name=drug_name,
        normalized_name=normalized_name,
        generic_name=ingredients[0] if ingredients else None,  # canonical casing from RxNorm
        rxcui=rxcui,
        ingredients=ingredients,
        brand_names=brand_names,
    )

    _cache[cache_key] = identity
    return identity

import logging
import os

import httpx

from backend.models.enums import InvestigateStatus, PrescriptionCheckStatus, ProfileType
from backend.models.report import InvestigateResponse, PrescriptionCheckResponse

logger = logging.getLogger(__name__)

# v1 entries use "v2:"; v2 reads and writes only "v4:" in the same Upstash instance.
# v4 (2026-10-21): responses carry verifier-cut claims (`removed`); no v3 entry lacking them is read.
CACHE_VERSION = "v4"

# Only these are cached (PROJECT.md Section 6), and only once verified (CP4).
CACHEABLE_STATUSES = {InvestigateStatus.ANSWERED, InvestigateStatus.PARTIAL}

TWELVE_HOURS_SECONDS = 12 * 60 * 60
THIRTY_DAYS_SECONDS = 30 * 24 * 60 * 60

# Prescription Check responses carry recalls, so they share the recall TTL.
PRESCRIPTION_CHECK_CACHE_TTL = TWELVE_HOURS_SECONDS

PROFILE_CACHE_TTLS = {
    ProfileType.FULL_INVESTIGATION: TWELVE_HOURS_SECONDS,
    ProfileType.RECALL_INVESTIGATION: TWELVE_HOURS_SECONDS,
    ProfileType.WARNINGS_REVIEW: THIRTY_DAYS_SECONDS,
    ProfileType.CONTRAINDICATIONS_REVIEW: THIRTY_DAYS_SECONDS,
    ProfileType.INTERACTION_INVESTIGATION: THIRTY_DAYS_SECONDS,
    ProfileType.ADVERSE_EVENT_INVESTIGATION: THIRTY_DAYS_SECONDS,
}

_UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
_UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
_redis_client: httpx.AsyncClient | None = None

if _UPSTASH_REDIS_REST_URL and _UPSTASH_REDIS_REST_TOKEN:
    _redis_client = httpx.AsyncClient(
        base_url=_UPSTASH_REDIS_REST_URL.rstrip("/"),
        headers={"Authorization": f"Bearer {_UPSTASH_REDIS_REST_TOKEN}"},
        timeout=5.0,
    )
else:
    logger.warning(
        "CACHE ERROR: Upstash Redis environment variables missing; report cache disabled"
    )


def build_cache_key(drug_name: str, profile: ProfileType) -> str:
    return f"{CACHE_VERSION}:{drug_name.lower()}:{profile.value}"


def _cache_ttl_for_profile(profile: ProfileType) -> int:
    return PROFILE_CACHE_TTLS[profile]


def is_cacheable(response: InvestigateResponse) -> bool:
    return response.status in CACHEABLE_STATUSES and response.meta.verified


async def _redis_get(cache_key: str) -> str | None:
    """Raw cached JSON, or None on a miss, a cache error, or no cache configured."""
    if _redis_client is None:
        logger.info("CACHE MISS: %s", cache_key)
        return None

    try:
        response = await _redis_client.post("/", json=["GET", cache_key])
        response.raise_for_status()
        response_body = response.json()
        if response_body.get("error"):
            raise RuntimeError(response_body["error"])

        cached_value = response_body.get("result")
        if cached_value is None:
            logger.info("CACHE MISS: %s", cache_key)
            return None

        logger.info("CACHE HIT: %s", cache_key)
        return cached_value
    except Exception as exc:
        logger.warning("CACHE ERROR: read failed for %s: %s", cache_key, exc)
        return None


async def _redis_set(cache_key: str, value: str, ttl_seconds: int) -> None:
    if _redis_client is None:
        return

    try:
        response = await _redis_client.post("/", json=["SET", cache_key, value, "EX", ttl_seconds])
        response.raise_for_status()
        response_body = response.json()
        if response_body.get("error"):
            raise RuntimeError(response_body["error"])

        logger.info("CACHE STORE: %s ttl=%s", cache_key, ttl_seconds)
    except Exception as exc:
        logger.warning("CACHE ERROR: store failed for %s: %s", cache_key, exc)


async def get_cached_response(cache_key: str) -> InvestigateResponse | None:
    cached_value = await _redis_get(cache_key)
    if cached_value is None:
        return None
    try:
        return InvestigateResponse.model_validate_json(cached_value)
    except Exception as exc:
        logger.warning("CACHE ERROR: read failed for %s: %s", cache_key, exc)
        return None


async def store_cached_response(
    cache_key: str,
    profile: ProfileType,
    investigate_response: InvestigateResponse,
) -> None:
    if not is_cacheable(investigate_response):
        return
    await _redis_set(cache_key, investigate_response.model_dump_json(), _cache_ttl_for_profile(profile))


# --- Prescription Check (owner note 2026-10-21): demo pairs can be pre-warmed ---

def build_prescription_cache_key(rxcuis: list[str]) -> str:
    """Keyed on the sorted resolved RxCUIs, so input order and spelling case don't matter."""
    return f"{CACHE_VERSION}:prescription_check:{','.join(sorted(set(rxcuis)))}"


def is_prescription_check_cacheable(response: PrescriptionCheckResponse) -> bool:
    return response.status == PrescriptionCheckStatus.COMPLETE and response.meta.verified


async def get_cached_prescription_check(cache_key: str) -> PrescriptionCheckResponse | None:
    cached_value = await _redis_get(cache_key)
    if cached_value is None:
        return None
    try:
        return PrescriptionCheckResponse.model_validate_json(cached_value)
    except Exception as exc:
        logger.warning("CACHE ERROR: read failed for %s: %s", cache_key, exc)
        return None


async def store_cached_prescription_check(cache_key: str, response: PrescriptionCheckResponse) -> None:
    if not is_prescription_check_cacheable(response):
        return
    await _redis_set(cache_key, response.model_dump_json(), PRESCRIPTION_CHECK_CACHE_TTL)


async def close_report_cache() -> None:
    if _redis_client is not None:
        await _redis_client.aclose()

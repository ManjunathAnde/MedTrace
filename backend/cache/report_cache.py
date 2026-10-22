import logging
import os

import httpx

from backend.models.enums import InvestigateStatus, ProfileType
from backend.models.report import InvestigateResponse

logger = logging.getLogger(__name__)

# v1 entries use "v2:"; v2 reads and writes only "v3:" in the same Upstash instance.
CACHE_VERSION = "v3"

# Only these are cached (PROJECT.md Section 6), and only once verified (CP4).
CACHEABLE_STATUSES = {InvestigateStatus.ANSWERED, InvestigateStatus.PARTIAL}

TWELVE_HOURS_SECONDS = 12 * 60 * 60
THIRTY_DAYS_SECONDS = 30 * 24 * 60 * 60

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


async def get_cached_response(cache_key: str) -> InvestigateResponse | None:
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

        cached = InvestigateResponse.model_validate_json(cached_value)
        logger.info("CACHE HIT: %s", cache_key)
        return cached
    except Exception as exc:
        logger.warning("CACHE ERROR: read failed for %s: %s", cache_key, exc)
        return None


async def store_cached_response(
    cache_key: str,
    profile: ProfileType,
    investigate_response: InvestigateResponse,
) -> None:
    if _redis_client is None or not is_cacheable(investigate_response):
        return

    ttl_seconds = _cache_ttl_for_profile(profile)
    try:
        response = await _redis_client.post(
            "/",
            json=["SET", cache_key, investigate_response.model_dump_json(), "EX", ttl_seconds],
        )
        response.raise_for_status()
        response_body = response.json()
        if response_body.get("error"):
            raise RuntimeError(response_body["error"])

        logger.info("CACHE STORE: %s ttl=%s", cache_key, ttl_seconds)
    except Exception as exc:
        logger.warning("CACHE ERROR: store failed for %s: %s", cache_key, exc)


async def close_report_cache() -> None:
    if _redis_client is not None:
        await _redis_client.aclose()

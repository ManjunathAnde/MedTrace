from dotenv import load_dotenv
load_dotenv()

import logging
import time

from cachetools import TTLCache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.apis.rxnorm import RxNormDrugNotFoundError, RxNormError
from backend.core.router import resolve_profile
from backend.llm.intent_classifier import classify_intent
from backend.llm.medication_extractor import extract_medication
from backend.llm.risk_analyst import generate_report
from backend.models.enums import ProfileType, SafetyDecision
from backend.models.report import MedicationReport
from backend.profiles import PROFILES
from backend.safety.filter import check_safety

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
REPORT_CACHE_TTL_SECONDS = 72 * 60 * 60  # 72 hours
FAIL_SAFE_REPORT_SUMMARY = "Report generation temporarily unavailable"
_report_cache = TTLCache(
    maxsize=200,
    ttl=REPORT_CACHE_TTL_SECONDS,
)

app = FastAPI(title="Medication Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvestigateRequest(BaseModel):
    query: str


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )


@app.post("/investigate")
async def investigate(request: InvestigateRequest) -> MedicationReport:
    t0 = time.perf_counter()
    query = request.query.strip()

    # Stage 1: Safety filter
    safety = await check_safety(query)
    if safety.decision == SafetyDecision.UNSAFE:
        return JSONResponse(
            status_code=403,
            content={"error": "unsafe_query", "reason": safety.reason},
        )

    # Stage 2: Medication name extraction
    drug_name = await extract_medication(query)

    # Stage 3: Intent classification
    intent = await classify_intent(query)

    # Stage 4: Profile routing
    profile = resolve_profile(intent)

    cache_key = f"{CACHE_VERSION}:{drug_name.lower()}:{profile.value}"
    if cache_key in _report_cache:
        logger.info("CACHE HIT: %s", cache_key)
        return _report_cache[cache_key]

    logger.info("CACHE MISS: %s", cache_key)

    # Stage 5: Evidence collection
    try:
        evidence = await PROFILES[profile](drug_name)
    except RxNormDrugNotFoundError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": "drug_not_found", "message": str(exc)},
        )
    except RxNormError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(exc)},
        )

    # Stage 6: Report generation
    report = await generate_report(evidence)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "query='%s' safety=%s drug_name='%s' profile=%s confidence=%.2f "
        "completeness=%.2f duration=%dms",
        query,
        safety.decision.value,
        drug_name,
        profile.value,
        intent.confidence,
        report.completeness_score,
        duration_ms,
    )

    if report.summary != FAIL_SAFE_REPORT_SUMMARY:
        _report_cache[cache_key] = report
    return report


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/profiles")
def list_profiles():
    return [p.value for p in ProfileType]

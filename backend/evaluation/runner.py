"""
Evaluation runner for the Medication Intelligence Agent.

Runs pipeline stages 1-5 (safety, extraction, intent, routing, retrieval)
against all 50 labeled queries in dataset.json. Stage 6 (generate_report)
is intentionally excluded to stay within the 15 RPM free-tier quota for
gemini-1.5-flash.

Usage:
    python -m backend.evaluation.runner

Output:
    backend/evaluation/evaluation_results.json
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
import json
import logging
import statistics
import time
from pathlib import Path

from backend.apis.rxnorm import RxNormDrugNotFoundError, RxNormError
from backend.core.router import resolve_profile
from backend.llm.intent_classifier import classify_intent
from backend.llm.medication_extractor import extract_medication
from backend.profiles import PROFILES
from backend.safety.filter import check_safety

DATASET_PATH = Path(__file__).parent / "dataset.json"
RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
DELAY_SECONDS = 45  # conservative delay accounting for multiple Gemini calls per query
PILOT_MAX_ID: int | None = 10  # Set to None to run all 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def run_query(entry: dict) -> dict:
    query = entry["query"]
    expected_safety = entry["expected_safety"]
    acceptable_profiles = entry.get("acceptable_profiles")  # list[str] | null
    expected_drug = entry.get("expected_drug")

    actual: dict = {
        "safety": None,
        "safety_classifier": None,
        "drug": None,
        "profile": None,
        "profile_confidence": None,
        "retrieval_success": None,
        "completeness_score": None,
    }
    failures: list[dict] = []
    t0 = time.perf_counter()

    try:
        # Stage 1: Safety filter
        safety_result = await check_safety(query)
        actual["safety"] = safety_result.decision.value
        actual["safety_classifier"] = safety_result.classifier.value

        if actual["safety"] != expected_safety:
            failures.append({
                "metric": "safety",
                "expected": expected_safety,
                "actual": actual["safety"],
            })

        # Only continue for queries the pipeline classified as safe
        if actual["safety"] == "safe":

            # Stage 2: Medication extraction
            drug_name = await extract_medication(query)
            actual["drug"] = drug_name

            if expected_drug is not None:
                if drug_name.lower() != expected_drug.lower():
                    failures.append({
                        "metric": "drug",
                        "expected": expected_drug,
                        "actual": drug_name,
                    })

            # Stage 3+4: Intent classification + profile routing
            intent = await classify_intent(query)
            profile = resolve_profile(intent)
            actual["profile"] = profile.value
            actual["profile_confidence"] = round(intent.confidence, 3)

            if acceptable_profiles is not None:
                if profile.value not in acceptable_profiles:
                    failures.append({
                        "metric": "intent",
                        "expected": acceptable_profiles,
                        "actual": profile.value,
                    })

            # Stage 5: Evidence retrieval (only for queries with a known expected drug)
            if expected_drug is not None:
                try:
                    evidence = await PROFILES[profile](drug_name)
                    actual["retrieval_success"] = True
                    actual["completeness_score"] = round(
                        evidence.metadata.completeness_score, 3
                    )
                except RxNormDrugNotFoundError as exc:
                    actual["retrieval_success"] = False
                    failures.append({
                        "metric": "retrieval",
                        "expected": "success",
                        "actual": f"drug_not_found: {exc}",
                    })
                except RxNormError as exc:
                    actual["retrieval_success"] = False
                    failures.append({
                        "metric": "retrieval",
                        "expected": "success",
                        "actual": f"rxnorm_error: {exc}",
                    })
                except Exception as exc:
                    actual["retrieval_success"] = False
                    failures.append({
                        "metric": "retrieval",
                        "expected": "success",
                        "actual": f"error: {exc}",
                    })

    except Exception as exc:
        logger.error("Unhandled error for query id=%d: %s", entry["id"], exc)
        failures.append({
            "metric": "pipeline",
            "expected": "no_error",
            "actual": str(exc),
        })

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "id": entry["id"],
        "query": query,
        "category": entry["category"],
        "expected": {
            "safety": expected_safety,
            "profiles": acceptable_profiles,
            "drug": expected_drug,
        },
        "actual": actual,
        "passed": len(failures) == 0,
        "latency_ms": latency_ms,
        "failures": failures,
    }


async def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if PILOT_MAX_ID is not None:
        dataset = [e for e in dataset if e["id"] <= PILOT_MAX_ID]
        logger.info("PILOT MODE: running IDs 1-%d only.", PILOT_MAX_ID)
    total = len(dataset)
    est_minutes = (total * DELAY_SECONDS) // 60
    logger.info(
        "Loaded %d queries. Estimated runtime: ~%d minutes.", total, est_minutes
    )

    results: list[dict] = []

    for i, entry in enumerate(dataset):
        logger.info(
            "[%d/%d] id=%d  %r",
            i + 1,
            total,
            entry["id"],
            entry["query"][:70],
        )
        result = await run_query(entry)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        logger.info(
            "  -> %s  safety=%s  profile=%s  drug=%r  latency=%.0fms",
            status,
            result["actual"]["safety"],
            result["actual"]["profile"],
            result["actual"]["drug"],
            result["latency_ms"],
        )
        if result["failures"]:
            for f in result["failures"]:
                logger.warning(
                    "     FAILURE metric=%s expected=%r actual=%r",
                    f["metric"],
                    f["expected"],
                    f["actual"],
                )

        if i < total - 1:
            await asyncio.sleep(DELAY_SECONDS)

    # ------------------------------------------------------------------ #
    # Aggregate metrics                                                    #
    # ------------------------------------------------------------------ #

    latencies = [r["latency_ms"] for r in results]

    # Safety: all 50 queries
    safety_correct = sum(
        1 for r in results
        if r["actual"]["safety"] == r["expected"]["safety"]
    )
    safety_accuracy = safety_correct / total

    # Intent: safe queries (by actual classification) with non-null acceptable_profiles
    intent_evals = [
        r for r in results
        if r["actual"]["safety"] == "safe" and r["expected"]["profiles"] is not None
    ]
    intent_correct = sum(
        1 for r in intent_evals
        if r["actual"]["profile"] in (r["expected"]["profiles"] or [])
    )
    intent_accuracy = intent_correct / len(intent_evals) if intent_evals else 0.0

    # Drug extraction: safe queries with a non-null expected_drug
    drug_evals = [
        r for r in results
        if r["actual"]["safety"] == "safe" and r["expected"]["drug"] is not None
    ]
    drug_correct = sum(
        1 for r in drug_evals
        if r["actual"]["drug"] is not None
        and r["actual"]["drug"].lower() == r["expected"]["drug"].lower()
    )
    drug_accuracy = drug_correct / len(drug_evals) if drug_evals else 0.0

    # Retrieval: queries where retrieval was attempted
    retrieval_evals = [
        r for r in results
        if r["actual"]["retrieval_success"] is not None
    ]
    retrieval_success_count = sum(
        1 for r in retrieval_evals if r["actual"]["retrieval_success"]
    )
    retrieval_rate = (
        retrieval_success_count / len(retrieval_evals) if retrieval_evals else 0.0
    )

    # Completeness: successful retrievals only
    completeness_scores = [
        r["actual"]["completeness_score"]
        for r in retrieval_evals
        if r["actual"]["completeness_score"] is not None
    ]
    avg_completeness = statistics.mean(completeness_scores) if completeness_scores else 0.0

    # Latency
    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    latencies_sorted = sorted(latencies)
    p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)
    p95_latency = latencies_sorted[p95_idx]

    # Failed cases: one entry per individual failure
    failed_cases = [
        {
            "id": r["id"],
            "query": r["query"],
            "category": r["category"],
            "metric": f["metric"],
            "expected": f["expected"],
            "actual": f["actual"],
        }
        for r in results
        for f in r["failures"]
    ]

    output = {
        "total_queries": total,
        "safety_accuracy": round(safety_accuracy, 4),
        "intent_accuracy": round(intent_accuracy, 4),
        "drug_extraction_accuracy": round(drug_accuracy, 4),
        "retrieval_success_rate": round(retrieval_rate, 4),
        "avg_completeness_score": round(avg_completeness, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "median_latency_ms": round(median_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "results": results,
        "failed_cases": failed_cases,
    }

    RESULTS_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Summary                                                              #
    # ------------------------------------------------------------------ #
    logger.info("=" * 55)
    logger.info("EVALUATION COMPLETE")
    logger.info("=" * 55)
    logger.info(
        "Safety accuracy:          %.1f%%  (%d/%d)",
        safety_accuracy * 100, safety_correct, total,
    )
    logger.info(
        "Intent accuracy:          %.1f%%  (%d/%d)",
        intent_accuracy * 100, intent_correct, len(intent_evals),
    )
    logger.info(
        "Drug extraction accuracy: %.1f%%  (%d/%d)",
        drug_accuracy * 100, drug_correct, len(drug_evals),
    )
    logger.info(
        "Retrieval success rate:   %.1f%%  (%d/%d)",
        retrieval_rate * 100, retrieval_success_count, len(retrieval_evals),
    )
    logger.info("Avg completeness score:   %.3f", avg_completeness)
    logger.info("Avg latency:              %.0f ms", avg_latency)
    logger.info("Median latency:           %.0f ms", median_latency)
    logger.info("P95 latency:              %.0f ms", p95_latency)
    logger.info("Total failures:           %d", len(failed_cases))
    logger.info("Results written to:       %s", RESULTS_PATH)


if __name__ == "__main__":
    asyncio.run(main())

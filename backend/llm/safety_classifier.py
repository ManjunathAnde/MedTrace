"""
Gemini Stage 2 safety classifier.

Called only when the Stage 1 rule engine finds no match. Fails closed on all
API errors, network failures, and response validation failures so that genuine
Gemini unavailability never permits an unsafe query through.

Retry policy: up to 3 attempts with linear backoff on ServerError (5xx).
ClientError (4xx, including 429) and ValidationError are not retried.
"""

import asyncio
import logging
import os
import time

from google import genai
from google.genai import errors as genai_errors, types
from pydantic import ValidationError

from backend.models.base import BaseSchema
from backend.models.classification import LLMCallDiagnostics, SafetyClassificationResult
from backend.models.enums import SafetyClassifierType, SafetyDecision

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_MAX_ATTEMPTS = 3

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a safety classifier for a medication information system.

## What this system does

This system retrieves factual, public-domain medication information from four
authoritative healthcare databases:
- RxNorm: drug identities and generic names
- DailyMed: FDA-approved prescribing labels (warnings, contraindications, interactions, precautions)
- FDA Enforcement: official recall and withdrawal records
- OpenFDA FAERS: publicly reported adverse event and safety signal data

## Central Reasoning Principle

Apply this single test to every query:

  SAFE   — The answer can be produced entirely from authoritative public medication
            data without knowing anything about the user's personal health, medical
            history, symptoms, diagnosis, age, or treatment situation.

  UNSAFE — Answering requires applying medical knowledge to a specific individual,
            or recommending a course of action for that individual.

This test is the only criterion that matters. Do not classify a query as UNSAFE
because the topic sounds dangerous, the drug sounds serious, or the wording
contains words like "warnings," "dangerous," "should not," or "contraindications."
Those words describe the factual content of prescribing labels, not personal advice.

## Query types that are always SAFE

The following query types ask for documented public information. Classify them SAFE
regardless of which drug is named or how the question is phrased:

1. Warning queries
   The user asks what warnings or hazards are documented for a drug.
   The answer comes from the DailyMed prescribing label. No personal information needed.
   SAFE: "What are the warnings for Ozempic?"
   SAFE: "Does warfarin have any serious warnings?"
   SAFE: "What hazards are listed for metformin?"

2. Contraindication queries
   The user asks who must not take a drug or what conditions prohibit its use.
   The answer lists population-level documented contraindications from the prescribing label.
   Asking who should NOT take a drug in general is asking for a documented list, not
   asking whether a specific person should take it.
   SAFE: "Who should not take metformin?"
   SAFE: "What are the contraindications for warfarin?"
   SAFE: "When is aspirin contraindicated?"

3. Drug interaction queries
   The user asks what drug interactions are documented for a medication.
   The answer comes from the prescribing label interaction section. No personal information needed.
   SAFE: "What drug interactions does warfarin have?"
   SAFE: "What drugs interact with Ozempic?"
   SAFE: "Are there known interactions for metformin?"

4. Adverse event and safety signal queries
   The user asks what adverse events or safety signals have been reported for a drug.
   The answer comes from OpenFDA FAERS public adverse event records. No personal information needed.
   SAFE: "What adverse events have been reported for metformin?"
   SAFE: "What safety signals exist for lisinopril in FAERS?"
   SAFE: "What side effects have been reported for Ozempic?"

5. Recall queries
   The user asks whether a drug has been recalled or subject to FDA enforcement action.
   The answer comes from FDA Enforcement records. No personal information needed.
   SAFE: "Has Ozempic been recalled?"
   SAFE: "Are there any recalls for metformin?"

6. General information queries
   The user asks for a broad overview or comprehensive information about a drug.
   SAFE: "Tell me everything about lisinopril"
   SAFE: "Investigate warfarin"

## Query types that are always UNSAFE

The following query types require information about a specific person and cannot be
answered from public data alone:

1. Personal medication decisions
   UNSAFE: "Should I take Ozempic?"
   UNSAFE: "Should my father take warfarin?"

2. Personal dosage guidance
   UNSAFE: "What dosage should I take?"
   UNSAFE: "How much metformin should I be taking?"

3. Personal stop, start, or change decisions
   UNSAFE: "Can I stop taking aspirin?"
   UNSAFE: "Should I switch from warfarin to a different medication?"

4. Advice tailored to an individual
   UNSAFE: "Is Ozempic right for me?"
   UNSAFE: "Is warfarin safe for my condition?"
   UNSAFE: "Is this safe for me personally?"

5. Medical emergency guidance
   UNSAFE: "I took too much warfarin — what do I do?"
   UNSAFE: "I think I overdosed."

6. Diagnosis requests
   UNSAFE: "Do I have diabetes?"
   UNSAFE: "Am I at risk for a clot?"

## The decisive distinction

SAFE queries ask: "What does the official medical record say about this drug?"
UNSAFE queries ask: "What should THIS PERSON do about this drug?"

Side-by-side:
  "What are the contraindications for warfarin?"    → SAFE  (asks for the documented list)
  "Do my contraindications rule out warfarin?"      → UNSAFE (asks about a specific person)

  "Who should not take metformin?"                  → SAFE  (asks for the population-level list)
  "Should I not take metformin?"                    → UNSAFE (asks about a specific person)

  "What are the warnings for Ozempic?"              → SAFE  (asks for prescribing-label content)
  "Is Ozempic too dangerous for me to take?"        → UNSAFE (asks for a personal risk assessment)

  "What drug interactions does warfarin have?"      → SAFE  (asks for the documented interaction list)
  "Is it safe for me to take warfarin with ibuprofen?" → UNSAFE (asks about a specific situation)

## Additional rules

- Unrecognized or misspelled drug name: classify based on query type, not drug name.
  The system resolves drug names independently. An unfamiliar drug name is not a safety concern.

- Genuine ambiguity: classify UNSAFE only when you cannot determine whether the query
  requests public factual data or personalized guidance. Do not classify UNSAFE merely
  because the subject matter sounds clinically sensitive.

- Medical emergencies: always classify UNSAFE when the user appears to be in or describing
  an immediate medical situation requiring action, regardless of phrasing.

User query: "{query}"
"""


class _GeminiSafetyResponse(BaseSchema):
    """Private schema for Gemini structured output. classifier is added in Python."""

    decision: SafetyDecision
    reason: str


def _fail_closed(
    duration_ms: float,
    attempts: int,
    api_error_type: str | None = None,
    validation_error: bool = False,
) -> SafetyClassificationResult:
    fallback_reason = "validation_error" if validation_error else "api_error"
    return SafetyClassificationResult(
        decision=SafetyDecision.UNSAFE,
        reason="safety_classifier_unavailable",
        classifier=SafetyClassifierType.GEMINI,
        diagnostics=LLMCallDiagnostics(
            model=_MODEL,
            duration_ms=round(duration_ms, 1),
            fallback_used=True,
            fallback_reason=fallback_reason,
            api_error_type=api_error_type,
            validation_error=validation_error,
            attempts=attempts,
        ),
    )


async def classify_safety(query: str) -> SafetyClassificationResult:
    """
    Classify a query using Gemini structured output.

    Retries up to _MAX_ATTEMPTS times on ServerError (5xx). ClientError (4xx)
    and ValidationError are not retried. Fails closed on exhaustion.
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _PROMPT_TEMPLATE.format(query=query)
    t_total = time.perf_counter()
    last_error_type: str | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_GeminiSafetyResponse,
                ),
            )
            raw = _GeminiSafetyResponse.model_validate_json(response.text)
            return SafetyClassificationResult(
                decision=raw.decision,
                reason=raw.reason,
                classifier=SafetyClassifierType.GEMINI,
                diagnostics=LLMCallDiagnostics(
                    model=_MODEL,
                    duration_ms=round((time.perf_counter() - t_total) * 1000, 1),
                    fallback_used=False,
                    fallback_reason=None,
                    api_error_type=None,
                    validation_error=False,
                    attempts=attempt,
                ),
            )
        except genai_errors.ServerError as exc:
            last_error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
            logger.warning(
                "  SAFETY attempt %d/%d failed: %s — %s",
                attempt,
                _MAX_ATTEMPTS,
                last_error_type,
                "retrying" if attempt < _MAX_ATTEMPTS else "giving up",
            )
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(attempt * 2)  # 2s after attempt 1, 4s after attempt 2
        except genai_errors.APIError as exc:
            # Non-retryable (429 quota, 400 bad request, etc.)
            return _fail_closed(
                (time.perf_counter() - t_total) * 1000,
                attempts=attempt,
                api_error_type=f"{type(exc).__name__}({getattr(exc, 'code', '?')})",
            )
        except ValidationError:
            return _fail_closed(
                (time.perf_counter() - t_total) * 1000,
                attempts=attempt,
                validation_error=True,
            )

    return _fail_closed(
        (time.perf_counter() - t_total) * 1000,
        attempts=_MAX_ATTEMPTS,
        api_error_type=last_error_type,
    )

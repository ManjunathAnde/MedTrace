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
# Medication Safety Classifier

Your job is **only** to determine whether a user's query can be answered by this medication information system.

Do **NOT** answer the query.

Return only whether the query is **SAFE** or **UNSAFE**.

---

# Decision Rule (Apply First)

Apply this single test to every query.

**SAFE**

The answer can be produced entirely from authoritative public medication information without evaluating or making recommendations about an identifiable individual.

Examples of authoritative public information include:

* FDA-approved prescribing information (DailyMed)
* FDA Recall Database
* OpenFDA FAERS adverse event reports
* Drug interaction information documented in prescribing labels
* Public medication identity information

The answer may describe warnings, contraindications, precautions, interactions, recalls, adverse events, approved labeling, documented risks, information about patient populations described in official labeling — provided it does NOT require evaluating a specific person's situation.

**UNSAFE**

The query requires evaluating, advising, or recommending something for an identifiable person. This includes deciding whether a specific individual should take, avoid, change, stop, start a medication, change dosage, seek emergency care, or applying medical knowledge to that person's own circumstances.

This distinction is the ONLY rule that matters.

Never classify a query as UNSAFE simply because the drug is high-risk, the condition is serious, or the wording includes: safe, dangerous, contraindicated, warning, risk, interaction. Those words frequently appear in FDA prescribing information.

---

# Three Levels of Questions

## Level 1 — Drug-Level Questions (Always SAFE)

These ask only about the medication itself.

SAFE: What are the warnings for Ozempic?
SAFE: What contraindications does warfarin have?
SAFE: What precautions are listed for metformin?
SAFE: What interactions are documented for aspirin?
SAFE: Has Ozempic been recalled?
SAFE: What adverse events have been reported for lisinopril?
SAFE: Tell me everything about warfarin.
SAFE: Investigate metformin.
SAFE: Explain Ozempic.
SAFE: Summarize the prescribing information for warfarin.

## Level 2 — Population-Level Questions (Always SAFE)

These ask what official medical documentation says about a patient population in general. They do NOT ask whether any specific person should take the medication. The answer comes directly from prescribing information.

SAFE: Who should not take metformin?
SAFE: What does the label say about metformin use in kidney disease?
SAFE: Is metformin contraindicated in patients with kidney disease?
SAFE: What precautions are listed for aspirin during pregnancy?
SAFE: What does the prescribing information say about warfarin use in pregnancy?
SAFE: What does the label say about pediatric use of aspirin?
SAFE: Are elderly patients mentioned in the prescribing information for lisinopril?
SAFE: Does the Ozempic label mention thyroid disease?
SAFE: What conditions are listed as contraindications for Ozempic?
SAFE: What populations require extra precautions when using warfarin?

Even though these mention diseases or patient groups, they remain SAFE because they request documented public information rather than advice for a specific individual.

## Level 3 — Individual Medical Advice (Always UNSAFE)

These require evaluating someone's own circumstances.

UNSAFE: Should I take Ozempic?
UNSAFE: Should my father take warfarin?
UNSAFE: Is Ozempic right for me?
UNSAFE: Is metformin safe for my kidneys?
UNSAFE: Is warfarin safe for my condition?
UNSAFE: Should I stop taking aspirin?
UNSAFE: Should I start metformin?
UNSAFE: Is it okay for me to take Ozempic?
UNSAFE: My mother has kidney disease. Should she take metformin?
UNSAFE: My doctor prescribed warfarin. Should I take it?

---

# Always SAFE Query Categories

## Warning Queries
SAFE: What are the warnings for Ozempic?
SAFE: What hazards are listed for metformin?
SAFE: Does warfarin have any serious warnings?
SAFE: What boxed warnings does aspirin have?
SAFE: What precautions are listed for lisinopril?

## Contraindication Queries
SAFE: Who should not take metformin?
SAFE: What are the contraindications for warfarin?
SAFE: When is aspirin contraindicated?
SAFE: What medical conditions prohibit Ozempic use?
SAFE: Which patients are listed as contraindicated for lisinopril?

## Drug Interaction Queries
SAFE: What drug interactions does warfarin have?
SAFE: What drugs interact with Ozempic?
SAFE: Are there known interactions for metformin?
SAFE: Does aspirin interact with ibuprofen?
SAFE: What interaction warnings are documented for lisinopril?

## Adverse Event Queries
SAFE: What adverse events have been reported for metformin?
SAFE: What safety signals exist for lisinopril in FAERS?
SAFE: What side effects have been reported for Ozempic?
SAFE: What adverse reactions are most frequently reported for warfarin?
SAFE: What does FAERS report for aspirin?

## Recall Queries
SAFE: Has Ozempic been recalled?
SAFE: Are there any recalls for metformin?
SAFE: Why was warfarin recalled?
SAFE: Has aspirin been subject to FDA enforcement?
SAFE: Has lisinopril ever been recalled?

## General Investigation Queries
SAFE: Investigate Ozempic.
SAFE: Analyze warfarin.
SAFE: Tell me everything about metformin.
SAFE: Summarize aspirin.
SAFE: Give me a complete overview of lisinopril.

## General Safety Profile Queries
The user asks whether a drug is generally safe or dangerous as a medication. The answer comes from the drug's documented safety profile. No individual patient information needed.

SAFE: Is Ozempic safe?
SAFE: Is warfarin dangerous?
SAFE: Is metformin a safe medication?
SAFE: Is aspirin safe?
SAFE: Is lisinopril a dangerous drug?

These become UNSAFE only when they reference a specific individual:
UNSAFE: Is Ozempic safe for me?
UNSAFE: Is warfarin safe for my condition?

The trigger for UNSAFE is "me", "my", "I" or a specific named individual — not the drug name or topic itself.

---

# Always UNSAFE Query Categories

## Personal Medication Decisions
UNSAFE: Should I take Ozempic?
UNSAFE: Should my father take warfarin?
UNSAFE: Should she continue aspirin?

## Dosage Advice
UNSAFE: What dosage should I take?
UNSAFE: How much metformin should I be taking?
UNSAFE: Is 10 mg enough for me?

## Start / Stop / Change
UNSAFE: Can I stop taking aspirin?
UNSAFE: Should I switch medications?
UNSAFE: Should I increase my dose?

## Personal Risk Assessment
UNSAFE: Is Ozempic right for me?
UNSAFE: Is warfarin safe for my condition?
UNSAFE: Is metformin safe for my kidneys?
UNSAFE: Is this medication appropriate for me?
UNSAFE: Should someone like me take Ozempic?

## Emergency Guidance
UNSAFE: I overdosed.
UNSAFE: I took too much warfarin.
UNSAFE: My child swallowed aspirin.
UNSAFE: What should I do right now?

## Diagnosis
UNSAFE: Do I have diabetes?
UNSAFE: Am I having a heart attack?
UNSAFE: Am I at risk for a stroke?

---

# Side-by-Side Boundary Examples

SAFE: What are the contraindications for warfarin?
UNSAFE: Do my medical conditions mean I should not take warfarin?

SAFE: What does the label say about metformin use in kidney disease?
UNSAFE: I have kidney disease. Should I take metformin?

SAFE: Who should not take Ozempic?
UNSAFE: Should I avoid Ozempic?

SAFE: What interactions are documented between warfarin and ibuprofen?
UNSAFE: Is it safe for me to take warfarin with ibuprofen?

SAFE: What precautions are listed for aspirin during pregnancy?
UNSAFE: I'm pregnant. Should I take aspirin?

SAFE: What adverse events have been reported for Ozempic?
UNSAFE: Do these side effects mean I should stop taking Ozempic?

SAFE: Is Ozempic safe?
UNSAFE: Is Ozempic safe for me?

SAFE: Is metformin safe for people with kidney disease?
UNSAFE: Is metformin safe for my kidney disease?

---

# Additional Rules

* Classify based on intent, not on the drug name.
* Unknown or misspelled drug names are NOT a safety concern.
* A mention of a disease, condition, pregnancy, age group, or patient population does NOT automatically make a query UNSAFE.
* Population-level questions about official prescribing information remain SAFE.
* Only classify UNSAFE when the user asks about an identifiable individual or requests a recommendation or course of action for that individual.
* Medical emergencies are always UNSAFE.
* Classify UNSAFE only when you cannot determine whether answering requires knowing anything about a specific identifiable person. Do not classify UNSAFE merely because the subject matter sounds clinically sensitive or the drug is high-risk.

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

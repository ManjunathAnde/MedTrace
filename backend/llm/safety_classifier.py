"""
Gemini Stage 2 safety classifier.

Called only when the Stage 1 rule engine finds no match. Fails closed on all
API errors, network failures, and response validation failures so that genuine
Gemini unavailability never permits an unsafe query through.
"""

import os

from google import genai
from google.genai import errors as genai_errors, types
from pydantic import ValidationError

from backend.models.base import BaseSchema
from backend.models.classification import SafetyClassificationResult
from backend.models.enums import SafetyClassifierType, SafetyDecision

_MODEL = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """\
You are a safety classifier for a medication information system.

The system provides factual, public-domain information about medications - warnings,
recalls, adverse events, interactions, and drug labels - all sourced from authoritative
healthcare APIs (RxNorm, DailyMed, FDA).

The system CANNOT and MUST NOT provide:
- Personal medical advice
- Dosage recommendations for a specific person
- Treatment or diagnosis recommendations
- Instructions to start, stop, change, or adjust any medication
- Emergency medical guidance

Classify the following user query as SAFE or UNSAFE.

SAFE: The query requests factual, public medication information the system is designed to provide.
Examples:
  - "What are the warnings for warfarin?" - requests documented warning information
  - "Investigate Ozempic" - requests medication overview
  - "Has Metformin been recalled?" - requests recall records
  - "Is Ozempic safe?" - requests the documented safety profile of a medication, which is
    factual public information about the drug, not advice for a specific person

UNSAFE: The query requests personal medical advice, dosage guidance for a specific person,
diagnosis, treatment recommendations, or emergency instructions.
Examples:
  - "Should I take Ozempic?" - asks whether a specific person should take a drug
  - "What dosage is right for me?" - asks for a personal dosage recommendation
  - "Can I stop warfarin?" - asks whether a specific person should stop a medication
  - "Is Ozempic safe for me?" - requests a personal safety assessment, not public drug information
  - "Is Ozempic safe for my condition?" - requests advice tailored to a specific individual

The key distinction: asking about a medication's documented safety profile is SAFE.
Asking whether a medication is safe for a specific person or situation is UNSAFE.

If the query does not clearly request personal medical advice, diagnosis, treatment,
dosage guidance, or emergency help — classify it as SAFE, even if the medication name
is unrecognized or misspelled. The system resolves drug names independently; unrecognized
names are not a safety concern.

If you are uncertain whether the query requests unsafe *content* (advice, diagnosis,
treatment), classify it as UNSAFE. Do not classify UNSAFE simply because the drug name
is unfamiliar.

If the query requests help for a possible medical emergency, classify it as UNSAFE regardless
of any medication names mentioned.

User query: "{query}"
"""


class _GeminiSafetyResponse(BaseSchema):
    """Private schema for Gemini structured output. classifier is added in Python."""

    decision: SafetyDecision
    reason: str


def _fail_closed() -> SafetyClassificationResult:
    return SafetyClassificationResult(
        decision=SafetyDecision.UNSAFE,
        reason="safety_classifier_unavailable",
        classifier=SafetyClassifierType.GEMINI,
    )


async def classify_safety(query: str) -> SafetyClassificationResult:
    """
    Classify a query using Gemini structured output.

    Catches only expected runtime failures (API errors, network errors,
    response validation errors). Programming errors propagate normally.
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _PROMPT_TEMPLATE.format(query=query)

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
    except genai_errors.APIError:
        return _fail_closed()
    except ValidationError:
        return _fail_closed()

    return SafetyClassificationResult(
        decision=raw.decision,
        reason=raw.reason,
        classifier=SafetyClassifierType.GEMINI,
    )

"""
Gemini Intent Classifier.

Receives a query already verified as SAFE by the safety filter.
Maps it to exactly one of the 6 predefined retrieval profiles.

Fails safe on all API errors, network failures, and response validation
failures — defaulting to full_investigation with confidence 0.0 so that
a Gemini outage never silently blocks a safe query.

The classifier never acts on confidence. Confidence routing belongs to
the orchestration layer.
"""

import os

from google import genai
from google.genai import errors as genai_errors, types
from pydantic import Field, ValidationError

from backend.models.base import BaseSchema
from backend.models.classification import IntentClassificationResult
from backend.models.enums import ProfileType

_MODEL = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """\
You are an intent classifier for a medication information system.

A user query has already been verified as safe. Your only task is to classify
the query into exactly one of 6 retrieval profiles.

Each profile triggers a fixed set of authoritative healthcare API calls. Choose
the profile whose retrieval scope best satisfies what the user is trying to learn.

PROFILES:

1. full_investigation
   Select when the user wants a comprehensive overview of a medication — covering
   identity, safety, recalls, interactions, and adverse events together. Also
   select this when the request is intentionally broad and cannot be satisfied
   by a single focused profile.
   Examples:
     - "Investigate Ozempic"
     - "Analyze Metformin"
     - "Tell me everything about Wegovy"
     - "Tell me everything important about semaglutide"

2. warnings_review
   Select when the user wants to understand the safety warnings documented in the
   medication's official prescribing label — boxed warnings, major precautions,
   and documented hazards.
   Examples:
     - "What are the warnings for warfarin?"
     - "Does Ozempic have any serious warnings?"
     - "Is warfarin dangerous?"

3. contraindications_review
   Select when the user wants to understand who must not take a medication or the
   conditions under which its use is prohibited or requires caution.
   Examples:
     - "Who should not take semaglutide?"
     - "What are the contraindications for Ozempic?"
     - "When is warfarin contraindicated?"

4. recall_investigation
   Select when the user wants to know whether a medication has been recalled,
   withdrawn, or subject to FDA enforcement action.
   Examples:
     - "Has Ozempic been recalled?"
     - "Why was Drug X recalled?"
     - "Any recalls for Metformin?"

5. interaction_investigation
   Select when the user wants to understand how a medication interacts with other
   drugs, as documented in the FDA-approved prescribing information.
   Examples:
     - "What interactions does warfarin have?"
     - "Are there serious interactions with Metformin?"
     - "What drugs interact with Ozempic?"

6. adverse_event_investigation
   Select when the user wants to understand adverse events or safety signals
   reported to the FDA's adverse event reporting system (FAERS).
   Examples:
     - "What adverse events for metformin?"
     - "What side effects have been reported for Ozempic?"
     - "What safety concerns exist for Wegovy?"

You must return exactly one of these six profile string values:
  full_investigation
  warnings_review
  contraindications_review
  recall_investigation
  interaction_investigation
  adverse_event_investigation

Choose the most specific profile that satisfies the request. Use
full_investigation only when the request is intentionally broad or cannot be
satisfied by a single focused profile.

Return a confidence score between 0.0 and 1.0.

Return a reason: one sentence explaining why this profile best satisfies the
retrieval intent of the query. Focus on what information the user is trying to
retrieve, not on vocabulary keywords.

User query: "{query}"
"""


class _GeminiIntentResponse(BaseSchema):
    """Private schema for Gemini structured output."""

    profile: ProfileType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


def _fail_safe() -> IntentClassificationResult:
    return IntentClassificationResult(
        profile=ProfileType.FULL_INVESTIGATION,
        confidence=0.0,
        reason="intent_classifier_unavailable",
    )


async def classify_intent(query: str) -> IntentClassificationResult:
    """
    Classify a safe query into one of the 6 retrieval profiles.

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
                response_schema=_GeminiIntentResponse,
            ),
        )
        raw = _GeminiIntentResponse.model_validate_json(response.text)
    except genai_errors.APIError:
        return _fail_safe()
    except ValidationError:
        return _fail_safe()

    return IntentClassificationResult(
        profile=raw.profile,
        confidence=raw.confidence,
        reason=raw.reason,
    )

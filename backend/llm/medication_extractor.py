"""
Medication Extractor — Stage 2 of the investigation pipeline.

Single responsibility: extract the primary drug name from a natural language query.
Returns a clean string ready for RxNorm lookup. Nothing else.

Fails safe: returns the raw query on Gemini failure so RxNorm can attempt
resolution directly. The caller handles RxNormDrugNotFoundError if it fails.
"""

import logging
import os
import time

from google import genai
from google.genai import errors as genai_errors, types

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
Extract the primary medication name from the following query.

Return ONLY the medication name — no explanation, no punctuation, no extra words.
If the query mentions multiple medications, return the one being primarily investigated.

Examples:
  "Investigate warfarin"                              → warfarin
  "What are the warnings for Ozempic?"                → Ozempic
  "Has semaglutide been recalled?"                    → semaglutide
  "What adverse events for metformin?"                → metformin
  "What interactions does warfarin have?"             → warfarin
  "Tell me everything about Wegovy"                   → Wegovy

Query: "{query}"
"""


async def extract_medication(query: str) -> str:
    """
    Extract the primary medication name from a natural language query.

    Fails safe: returns the raw query if Gemini is unavailable, allowing
    RxNorm to attempt resolution directly.
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _PROMPT_TEMPLATE.format(query=query)
    t0 = time.perf_counter()

    try:
        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )
        extracted = (response.text or "").strip().strip('"').strip("'").strip()
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        result = extracted if extracted else query
        logger.info(
            "  EXTRACT diag: model=%s duration_ms=%.1f fallback=False result=%r",
            _MODEL,
            duration_ms,
            result,
        )
        return result
    except genai_errors.APIError as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        api_error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
        logger.warning(
            "  EXTRACT diag: model=%s duration_ms=%.1f fallback=True api_error=%s returning raw query",
            _MODEL,
            duration_ms,
            api_error_type,
        )
        return query

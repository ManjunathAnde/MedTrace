"""
Medication Extractor — Stage 2 of the investigation pipeline.

Single responsibility: extract the primary drug name from a natural language query.
Returns a clean string ready for RxNorm lookup. Nothing else.

Fails safe: returns the raw query on Gemini failure so RxNorm can attempt
resolution directly. The caller handles RxNormDrugNotFoundError if it fails.

Retry policy: up to 3 attempts with linear backoff on ServerError (5xx).
ClientError (4xx, including 429) is not retried.
"""

import asyncio
import logging
import os
import time

from google import genai
from google.genai import errors as genai_errors, types

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_MAX_ATTEMPTS = 3

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

    Retries up to _MAX_ATTEMPTS times on ServerError (5xx). Fails safe by
    returning the raw query if all attempts fail, allowing RxNorm to attempt
    resolution directly.
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _PROMPT_TEMPLATE.format(query=query)
    t_total = time.perf_counter()

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0),
            )
            extracted = (response.text or "").strip().strip('"').strip("'").strip()
            result = extracted if extracted else query
            duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
            logger.info(
                "  EXTRACT diag: model=%s duration_ms=%.1f fallback=False attempts=%d result=%r",
                _MODEL,
                duration_ms,
                attempt,
                result,
            )
            return result
        except genai_errors.ServerError as exc:
            error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
            logger.warning(
                "  EXTRACT attempt %d/%d failed: %s — %s",
                attempt,
                _MAX_ATTEMPTS,
                error_type,
                "retrying" if attempt < _MAX_ATTEMPTS else "giving up",
            )
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(attempt * 2)
        except genai_errors.APIError as exc:
            error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
            duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
            logger.warning(
                "  EXTRACT diag: model=%s duration_ms=%.1f fallback=True attempts=%d api_error=%s returning raw query",
                _MODEL,
                duration_ms,
                attempt,
                error_type,
            )
            return query

    duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
    logger.warning(
        "  EXTRACT diag: model=%s duration_ms=%.1f fallback=True attempts=%d all ServerErrors — returning raw query",
        _MODEL,
        duration_ms,
        _MAX_ATTEMPTS,
    )
    return query

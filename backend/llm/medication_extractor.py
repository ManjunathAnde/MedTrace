"""
Medication Extractor — Stage 2 of the investigation pipeline.

Single responsibility: extract the primary drug name from a natural language query.
Returns a clean string ready for RxNorm lookup. Nothing else.

Fails safe: returns the raw query on Gemini failure so RxNorm can attempt
resolution directly. The caller handles RxNormDrugNotFoundError if it fails.

Retry policy: up to 3 attempts with linear backoff on ServerError (5xx).
ClientError(429) triggers Groq fallback instead of immediate fail-safe.
All other ClientErrors (4xx) are not retried.
"""

import asyncio
import logging
import os
import time

import groq as groq_sdk
from google import genai
from google.genai import errors as genai_errors, types

from backend.llm.groq_client import _GROQ_MODEL, get_groq_client

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


async def _try_groq_extract(
    query: str,
    original_api_error: str,
    gemini_attempts: int,
) -> str:
    """
    Groq fallback for Gemini 429. Returns raw query on any Groq error so
    RxNorm can attempt resolution directly.
    """
    t_groq = time.perf_counter()
    try:
        client = get_groq_client()
        prompt = _PROMPT_TEMPLATE.format(query=query)
        response = await client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip()
        # Qwen3 thinking models include <think>...</think> in plain-text responses.
        # The actual answer follows the closing tag.
        if "</think>" in content:
            content = content.split("</think>", 1)[1].strip()
        extracted = content.strip('"').strip("'").strip()
        result = extracted if extracted else query
        duration_ms = round((time.perf_counter() - t_groq) * 1000, 1)
        logger.info(
            "  EXTRACT Groq fallback: model=%s duration_ms=%.1f result=%r",
            _GROQ_MODEL,
            duration_ms,
            result,
        )
        return result
    except (groq_sdk.APIStatusError, groq_sdk.APIConnectionError) as exc:
        logger.warning(
            "  EXTRACT Groq fallback API error: %s — returning raw query", exc
        )
        return query
    except KeyError:
        logger.warning("  EXTRACT Groq fallback failed: GROQ_API_KEY not set — returning raw query")
        return query
    except Exception as exc:
        logger.warning(
            "  EXTRACT Groq fallback unexpected error: %s — returning raw query", exc
        )
        return query


async def extract_medication(query: str) -> str:
    """
    Extract the primary medication name from a natural language query.

    Retries up to _MAX_ATTEMPTS times on ServerError (5xx). On ClientError(429)
    falls back to Groq. Fails safe by returning the raw query if all attempts
    fail, allowing RxNorm to attempt resolution directly.
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
            api_error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
            if getattr(exc, "code", None) == 429:
                logger.warning(
                    "  EXTRACT Gemini 429 on attempt %d — trying Groq fallback", attempt
                )
                return await _try_groq_extract(query, api_error_type, attempt)
            # Other ClientErrors — fail safe immediately
            duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
            logger.warning(
                "  EXTRACT diag: model=%s duration_ms=%.1f fallback=True attempts=%d api_error=%s returning raw query",
                _MODEL,
                duration_ms,
                attempt,
                api_error_type,
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

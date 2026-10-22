"""
Medication Extractor — Stage 2 of the investigation pipeline.

Single responsibility: extract the primary drug name from a natural language query.
Returns a clean string ready for RxNorm lookup. Nothing else.

Fails safe: returns the raw query on Gemini failure so RxNorm can attempt
resolution directly. The caller handles RxNormDrugNotFoundError if it fails.

Retry policy: up to 3 attempts with linear backoff on ServerError (5xx).
Transient Gemini provider failures trigger Groq fallback instead of immediate
fail-safe. All other ClientErrors (4xx) are not retried.
"""

import asyncio
import logging
import os
import time

import groq as groq_sdk
from google import genai
from google.genai import errors as genai_errors, types

from backend.llm.groq_client import (
    _GROQ_MODEL,
    TRANSIENT_GEMINI_NETWORK_ERRORS,
    gemini_fallback_reason,
    get_groq_client,
    is_transient_gemini_error,
)
from backend.llm.providers import EXTRACTION_MAX_OUTPUT_TOKENS, Provider, complete_json
from backend.models.classification import ExtractedDrugs

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
    fallback_reason: str,
) -> str:
    """
    Groq fallback for transient Gemini provider failures. Returns raw query on
    any Groq error so RxNorm can attempt resolution directly.
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
            "  EXTRACT Groq fallback: model=%s duration_ms=%.1f fallback_reason=%s result=%r",
            _GROQ_MODEL,
            duration_ms,
            fallback_reason,
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

    Retries up to _MAX_ATTEMPTS times on ServerError (5xx). Transient Gemini
    provider failures fall back to Groq. Fails safe by returning the raw query
    if all attempts fail, allowing RxNorm to attempt resolution directly.
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
            elif is_transient_gemini_error(exc):
                fallback_reason = gemini_fallback_reason(exc)
                logger.warning(
                    "  EXTRACT Gemini provider failure detected after %d attempts: %s",
                    attempt,
                    error_type,
                )
                logger.warning("  EXTRACT Attempting Groq fallback")
                return await _try_groq_extract(query, error_type, attempt, fallback_reason)
        except genai_errors.APIError as exc:
            api_error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
            if is_transient_gemini_error(exc):
                fallback_reason = gemini_fallback_reason(exc)
                logger.warning(
                    "  EXTRACT Gemini provider failure detected on attempt %d: %s",
                    attempt,
                    api_error_type,
                )
                logger.warning("  EXTRACT Attempting Groq fallback")
                return await _try_groq_extract(query, api_error_type, attempt, fallback_reason)
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
        except TRANSIENT_GEMINI_NETWORK_ERRORS as exc:
            api_error_type = type(exc).__name__
            fallback_reason = gemini_fallback_reason(exc)
            logger.warning(
                "  EXTRACT Gemini provider failure detected on attempt %d: %s",
                attempt,
                api_error_type,
            )
            logger.warning("  EXTRACT Attempting Groq fallback")
            return await _try_groq_extract(query, api_error_type, attempt, fallback_reason)

    duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
    logger.warning(
        "  EXTRACT diag: model=%s duration_ms=%.1f fallback=True attempts=%d all ServerErrors — returning raw query",
        _MODEL,
        duration_ms,
        _MAX_ATTEMPTS,
    )
    return query


# --- v2 extraction (PROJECT.md Sections 5.2, 12.2) ---
# Verbatim list on providers.py plus a code guard. Replaces extract_medication
# once /investigate is rewired. Both providers failing raises
# ProvidersUnavailableError; the caller reports UNAVAILABLE and never uses the
# raw query as a drug name.

# PROJECT.md Section 12.2, verbatim. {query} is substituted with str.replace
# because the prompt contains JSON braces.
_EXTRACTION_PROMPT = """\
You extract medication names from a user's message. You copy text. You do not interpret it.

RULES
1. Copy each medication name EXACTLY as the user typed it, character for character, including any misspellings. Never correct spelling. Never expand abbreviations. Never convert brand names to generic names or the reverse.
2. Extract only names the user explicitly typed. Never infer a medication from a description.
   - "my blood pressure pill" -> extract nothing
   - "statins", "NSAIDs", "antibiotics" -> extract nothing (drug classes, not medications)
3. Exclude strength, dose, and form. Extract the name only.
   - "Tylenol 500mg tablets" -> "Tylenol"
   - Keep multi-word product names whole: "Tylenol PM" -> "Tylenol PM"
4. Do not extract foods, drinks, or other substances: alcohol, coffee, grapefruit, nicotine.
5. If a name appears more than once, extract it once.
6. If no medication name is present, return an empty list. An empty list is a correct answer. Never guess to avoid it.

OUTPUT
Return only JSON: {"drugs": ["name1", "name2"]}

EXAMPLES
User: "Can I take ibuprofen with lisinopril?"
{"drugs": ["ibuprofen", "lisinopril"]}

User: "What are the boxed warnings for warfrin?"
{"drugs": ["warfrin"]}

User: "Is Eliquis 5mg safe with grapefruit juice?"
{"drugs": ["Eliquis"]}

User: "Does Tylenol PM interact with Zoloft?"
{"drugs": ["Tylenol PM", "Zoloft"]}

User: "What should I know about my heart medication?"
{"drugs": []}

User: "Are statins safe with alcohol?"
{"drugs": []}

USER MESSAGE
{query}
"""


def build_extraction_prompt(query: str) -> str:
    return _EXTRACTION_PROMPT.replace("{query}", query)


def is_plausible_name(name: str) -> bool:
    n = name.strip()
    return 2 <= len(n) <= 60 and any(c.isalpha() for c in n) and not n.isdigit()


def validate_extraction(query: str, drugs: list[str]) -> list[str]:
    """
    Code guard (Section 5.2): keep only names that appear in the user's text
    (case-insensitive), dedupe, and drop implausible names. The LLM may not
    "correct" a name: "warfarin" for the query "warfrin" is dropped.
    """
    q = query.lower()
    valid = [d.strip() for d in drugs if d.strip() and d.strip().lower() in q]
    rejected = [d for d in drugs if d.strip() not in valid]
    if rejected:
        logger.warning("extractor_rejected: %s", rejected)
    valid = list(dict.fromkeys(valid))
    return [d for d in valid if is_plausible_name(d)]


async def extract_medication_names(query: str) -> tuple[list[str], Provider]:
    """Verbatim extraction plus the code guard, with the provider used."""
    extracted, provider = await complete_json(
        build_extraction_prompt(query), ExtractedDrugs, EXTRACTION_MAX_OUTPUT_TOKENS
    )
    drugs = validate_extraction(query, extracted.drugs)
    logger.info("extraction drugs=%s provider=%s", drugs, provider)
    return drugs, provider

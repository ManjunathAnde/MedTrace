"""
LLM providers (PROJECT.md Section 12): the one place that sets provider order
and call parameters. Every v2 LLM call goes through complete_json.

  - Gemini first, Groq fallback, for every call (no job is tied to one provider)
  - temperature 0; JSON output validated against the caller's Pydantic schema
  - invalid JSON or a schema mismatch is retried once on the same provider,
    then the next provider is tried; an API, network or configuration error
    moves to the next provider straight away
  - Groq: JSON mode, explicit max_tokens under the output-token limit,
    reasoning_effort only for Qwen models

Keys and models come from the environment at call time (GOOGLE_API_KEY,
GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL). Drug-agnostic: the verifier may import it.
"""

import json
import logging
import os
import time
from typing import Literal, TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from groq import AsyncGroq, GroqError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

Provider = Literal["gemini", "groq"]
PROVIDER_ORDER: tuple[Provider, ...] = ("gemini", "groq")

# Groq's output-token limit on the current tier (1000/min); one call must stay under it.
GROQ_MAX_OUTPUT_TOKENS = 1000

# Per-call output budgets for one Ask request. The small helpers stay small so
# the synthesizer gets the rest of Groq's 1000 output tokens/min. Safety needs
# 128: Gemini's one-sentence safety_reason truncated the JSON at 64 (measured).
SAFETY_MAX_OUTPUT_TOKENS = 128
EXTRACTION_MAX_OUTPUT_TOKENS = 96
INTENT_MAX_OUTPUT_TOKENS = 96
SYNTHESIZER_MAX_OUTPUT_TOKENS = (
    GROQ_MAX_OUTPUT_TOKENS
    - SAFETY_MAX_OUTPUT_TOKENS
    - EXTRACTION_MAX_OUTPUT_TOKENS
    - INTENT_MAX_OUTPUT_TOKENS
)
_ATTEMPTS_PER_PROVIDER = 2  # first call + one retry on invalid JSON / schema mismatch

T = TypeVar("T", bound=BaseModel)


class ProvidersUnavailableError(Exception):
    """Every provider failed; the caller reports UNAVAILABLE."""


def groq_prompt(prompt: str, schema: type[BaseModel]) -> str:
    # Groq JSON mode needs "JSON" in the prompt and has no schema parameter.
    return (
        f"{prompt}\n\nReturn JSON only, matching this JSON schema:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )


def groq_request_params(
    model: str, prompt: str, schema: type[BaseModel], max_output_tokens: int
) -> dict:
    """Groq chat.completions parameters; sends only what the model supports."""
    params = {
        "model": model,
        "messages": [{"role": "user", "content": groq_prompt(prompt, schema)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "max_tokens": max_output_tokens,
    }
    if "qwen" in model.lower():
        params["reasoning_effort"] = "none"
    return params


async def _call_gemini(prompt: str, schema: type[BaseModel], max_output_tokens: int) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = await client.aio.models.generate_content(
        model=os.environ["GEMINI_MODEL"],
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_output_tokens,
        ),
    )
    return response.text or ""


async def _call_groq(prompt: str, schema: type[BaseModel], max_output_tokens: int) -> str:
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    response = await client.chat.completions.create(
        **groq_request_params(os.environ["GROQ_MODEL"], prompt, schema, max_output_tokens)
    )
    return response.choices[0].message.content or ""


_CALLS = {"gemini": _call_gemini, "groq": _call_groq}

# Errors that mean "this provider is unavailable now": move to the next one.
_PROVIDER_ERRORS: dict[Provider, tuple[type[BaseException], ...]] = {
    "gemini": (genai_errors.APIError, httpx.HTTPError, KeyError),
    "groq": (GroqError, httpx.HTTPError, KeyError),
}


def _describe(exc: BaseException) -> str:
    if isinstance(exc, KeyError):
        return f"missing env var {exc}"
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return f"{type(exc).__name__}({code})" if code else type(exc).__name__


async def complete_json(
    prompt: str, schema: type[T], max_output_tokens: int
) -> tuple[T, Provider]:
    """
    Run one JSON call, Gemini first then Groq, and return the validated result
    with the provider that produced it.

    Raises:
      ValueError                 -> max_output_tokens over GROQ_MAX_OUTPUT_TOKENS
      ProvidersUnavailableError  -> every provider failed
    """
    if not 0 < max_output_tokens <= GROQ_MAX_OUTPUT_TOKENS:
        raise ValueError(
            f"max_output_tokens must be 1..{GROQ_MAX_OUTPUT_TOKENS}, got {max_output_tokens}"
        )

    failures: list[str] = []
    for provider in PROVIDER_ORDER:
        for attempt in range(1, _ATTEMPTS_PER_PROVIDER + 1):
            started = time.perf_counter()
            try:
                raw = await _CALLS[provider](prompt, schema, max_output_tokens)
            except _PROVIDER_ERRORS[provider] as exc:
                reason = _describe(exc)
                logger.warning("LLM %s unavailable (%s) schema=%s", provider, reason, schema.__name__)
                failures.append(f"{provider}: {reason}")
                break
            try:
                result = schema.model_validate_json(raw)
            except ValidationError as exc:
                logger.warning(
                    "LLM %s invalid output attempt %d/%d schema=%s errors=%d",
                    provider, attempt, _ATTEMPTS_PER_PROVIDER, schema.__name__, exc.error_count(),
                )
                failures.append(f"{provider}: invalid output (attempt {attempt})")
                continue
            logger.info(
                "LLM ok provider=%s schema=%s attempt=%d duration_ms=%.1f",
                provider, schema.__name__, attempt, (time.perf_counter() - started) * 1000,
            )
            return result, provider

    raise ProvidersUnavailableError("; ".join(failures))

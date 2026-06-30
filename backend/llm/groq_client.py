"""
Groq client factory.

Provides a shared AsyncGroq client and model constant used exclusively as a
fallback when Gemini has a transient provider/runtime failure.
"""

import os

import httpx
from google.genai import errors as genai_errors
from groq import AsyncGroq

_GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
TRANSIENT_GEMINI_STATUS_CODES = {408, 429, 500, 502, 503, 504}
TRANSIENT_GEMINI_NETWORK_ERRORS = (httpx.TimeoutException, httpx.ConnectError)


def get_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=os.environ["GROQ_API_KEY"])


def is_transient_gemini_error(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return getattr(exc, "code", None) in TRANSIENT_GEMINI_STATUS_CODES
    return isinstance(exc, TRANSIENT_GEMINI_NETWORK_ERRORS)


def gemini_fallback_reason(exc: BaseException) -> str:
    if isinstance(exc, genai_errors.APIError):
        return f"gemini_{getattr(exc, 'code', '?')}"
    return "gemini_network_error"

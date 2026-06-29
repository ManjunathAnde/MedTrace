"""
Groq client factory.

Provides a shared AsyncGroq client and model constant used exclusively as a
fallback when Gemini returns ClientError(429). Not called on any other error.
"""

import os

from groq import AsyncGroq

_GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")


def get_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

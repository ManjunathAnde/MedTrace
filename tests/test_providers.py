"""Provider call parameters (PROJECT.md §12): pure parts of backend/llm/providers.py."""

import asyncio

import pytest
from pydantic import BaseModel

from backend.llm.providers import (
    EXTRACTION_MAX_OUTPUT_TOKENS,
    GROQ_MAX_OUTPUT_TOKENS,
    INTENT_MAX_OUTPUT_TOKENS,
    PROVIDER_ORDER,
    SAFETY_MAX_OUTPUT_TOKENS,
    SYNTHESIZER_MAX_OUTPUT_TOKENS,
    complete_json,
    groq_request_params,
)


class _Answer(BaseModel):
    word: str


def test_provider_order_is_gemini_then_groq():
    assert PROVIDER_ORDER == ("gemini", "groq")


def test_groq_params_for_qwen_include_reasoning_effort():
    params = groq_request_params("qwen/qwen3.8-27b", "Say ok.", _Answer, 300)
    assert params["reasoning_effort"] == "none"
    assert params["temperature"] == 0
    assert params["max_tokens"] == 300
    assert params["response_format"] == {"type": "json_object"}


def test_groq_params_for_other_models_omit_reasoning_effort():
    params = groq_request_params("llama-3.3-70b-versatile", "Say ok.", _Answer, 300)
    assert "reasoning_effort" not in params
    assert params["max_tokens"] == 300 and params["temperature"] == 0


def test_groq_prompt_names_json_and_carries_schema():
    content = groq_request_params("qwen/qwen3.8-27b", "Say ok.", _Answer, 300)["messages"][0]["content"]
    assert content.startswith("Say ok.")
    assert "JSON" in content and '"word"' in content


@pytest.mark.parametrize("tokens", [0, GROQ_MAX_OUTPUT_TOKENS + 1])
def test_max_output_tokens_outside_limit_rejected_before_any_call(tokens):
    with pytest.raises(ValueError):
        asyncio.run(complete_json("Say ok.", _Answer, tokens))


def test_ask_request_budgets_fit_groq_output_limit():
    budgets = [
        SAFETY_MAX_OUTPUT_TOKENS,
        EXTRACTION_MAX_OUTPUT_TOKENS,
        INTENT_MAX_OUTPUT_TOKENS,
        SYNTHESIZER_MAX_OUTPUT_TOKENS,
    ]
    assert all(b > 0 for b in budgets)
    assert sum(budgets) <= GROQ_MAX_OUTPUT_TOKENS
    assert SYNTHESIZER_MAX_OUTPUT_TOKENS > max(budgets[:3])

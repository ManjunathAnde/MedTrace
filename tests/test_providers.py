"""Provider call parameters (PROJECT.md §12): pure parts of backend/llm/providers.py."""

import asyncio

import pytest
from pydantic import BaseModel

from backend.llm.providers import (
    GROQ_MAX_OUTPUT_TOKENS,
    PROVIDER_ORDER,
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

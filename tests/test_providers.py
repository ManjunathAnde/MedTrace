"""Provider call parameters and Groq retry rules (PROJECT.md §12, §8 rule 6): backend/llm/providers.py, network mocked."""

import asyncio

import httpx
import pytest
from groq import APIConnectionError, APITimeoutError, BadRequestError, InternalServerError, RateLimitError
from pydantic import BaseModel

import backend.llm.providers as providers
from backend.llm.providers import (
    EXTRACTION_MAX_OUTPUT_TOKENS,
    GROQ_MAX_OUTPUT_TOKENS,
    INTENT_MAX_OUTPUT_TOKENS,
    PROVIDER_ORDER,
    ProvidersUnavailableError,
    SAFETY_MAX_OUTPUT_TOKENS,
    SYNTHESIZER_MAX_OUTPUT_TOKENS,
    complete_json,
    groq_daily_limit_hit,
    groq_rate_limit_wait_s,
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


# --- Groq 429: wait out the window, retry Groq once (mocked) ---

def _rate_limit_error(headers: dict | None = None, message: str = "Rate limit reached") -> RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, headers=headers or {}, request=request)
    return RateLimitError(message, response=response, body=None)


@pytest.mark.parametrize("headers,message,wait", [
    ({"retry-after": "7"}, "Rate limit reached", 7.0),
    ({}, "Requested 1795. Please try again in 7.66s.", 7.66),
    ({}, "Please try again in 1m2.5s.", 62.5),
    ({}, "Please try again in 450ms.", 0.45),
    ({"retry-after": "600"}, "Rate limit reached", 65.0),
    ({}, "Rate limit reached", 65.0),
])
def test_groq_rate_limit_wait_reads_header_then_message_capped_at_65(headers, message, wait):
    assert groq_rate_limit_wait_s(_rate_limit_error(headers, message)) == pytest.approx(wait)


def _mock_providers(monkeypatch, groq_outcomes: list, sleeps: list):
    async def gemini_quota_exhausted(*args):
        raise httpx.ConnectError("gemini down")

    async def groq(*args):
        outcome = groq_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setitem(providers._CALLS, "gemini", gemini_quota_exhausted)
    monkeypatch.setattr(providers, "_call_groq", groq)
    monkeypatch.setattr(providers.asyncio, "sleep", fake_sleep)


def test_groq_429_waits_and_retries_once_then_succeeds(monkeypatch):
    sleeps = []
    _mock_providers(monkeypatch, [_rate_limit_error({}, "Please try again in 7.66s."), '{"word": "ok"}'], sleeps)
    result, provider = asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert (result.word, provider, sleeps) == ("ok", "groq", [pytest.approx(7.66)])


def test_groq_429_twice_is_unavailable_after_one_wait(monkeypatch):
    sleeps = []
    _mock_providers(monkeypatch, [_rate_limit_error({"retry-after": "3"}), _rate_limit_error({"retry-after": "3"})], sleeps)
    with pytest.raises(ProvidersUnavailableError):
        asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert sleeps == [3.0]


# --- Groq daily limit fails at once; 5xx/timeout/connection retry once after 2s (mocked) ---

def _daily_limit_error(kind: str) -> RateLimitError:
    unit = {"TPD": "tokens per day", "RPD": "requests per day"}[kind]
    return _rate_limit_error({}, (
        "Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_test` service tier "
        f"`on_demand` on {unit} ({kind}): Limit 500000, Used 499800, Requested 1200. "
        "Please try again in 7m32.4s."))


def _server_error(status: int = 500) -> InternalServerError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return InternalServerError("Internal Server Error", response=httpx.Response(status, request=request), body=None)


@pytest.mark.parametrize("kind", ["TPD", "RPD"])
def test_groq_daily_limit_429_fails_at_once_without_waiting(monkeypatch, kind):
    sleeps, outcomes = [], [_daily_limit_error(kind)]
    _mock_providers(monkeypatch, outcomes, sleeps)
    with pytest.raises(ProvidersUnavailableError):
        asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert (sleeps, outcomes) == ([], [])  # one Groq call, no wait


def test_daily_limit_detection_ignores_per_minute_429():
    assert groq_daily_limit_hit(_daily_limit_error("TPD")) == "TPD"
    assert groq_daily_limit_hit(_daily_limit_error("RPD")) == "RPD"
    per_minute = "Rate limit reached ... on tokens per minute (TPM): Limit 8000. Please try again in 7.66s."
    assert groq_daily_limit_hit(_rate_limit_error({}, per_minute)) is None


@pytest.mark.parametrize("error", [
    _server_error(500),
    _server_error(503),
    APITimeoutError(request=httpx.Request("POST", "https://api.groq.com")),
    APIConnectionError(request=httpx.Request("POST", "https://api.groq.com")),
])
def test_groq_transient_error_waits_2s_and_retries_once_then_succeeds(monkeypatch, error):
    sleeps, outcomes = [], [error, '{"word": "ok"}']
    _mock_providers(monkeypatch, outcomes, sleeps)
    result, provider = asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert (result.word, provider, sleeps, outcomes) == ("ok", "groq", [pytest.approx(2.0)], [])


def test_groq_500_twice_is_unavailable_after_one_wait(monkeypatch):
    sleeps, outcomes = [], [_server_error(500), _server_error(500)]
    _mock_providers(monkeypatch, outcomes, sleeps)
    with pytest.raises(ProvidersUnavailableError):
        asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert (sleeps, outcomes) == ([pytest.approx(2.0)], [])


def test_groq_other_4xx_is_not_retried(monkeypatch):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    bad_request = BadRequestError("Bad Request", response=httpx.Response(400, request=request), body=None)
    sleeps, outcomes = [], [bad_request]
    _mock_providers(monkeypatch, outcomes, sleeps)
    with pytest.raises(ProvidersUnavailableError):
        asyncio.run(complete_json("Say ok.", _Answer, 100))
    assert (sleeps, outcomes) == ([], [])


def test_groq_client_has_sdk_retries_off(monkeypatch):
    created = {}

    class FakeCompletions:
        async def create(self, **params):
            message = type("M", (), {"content": '{"word": "ok"}'})
            return type("R", (), {"choices": [type("C", (), {"message": message})]})

    class FakeAsyncGroq:
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})

    monkeypatch.setattr(providers, "AsyncGroq", FakeAsyncGroq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    assert asyncio.run(providers._call_groq("Say ok.", _Answer, 100)) == '{"word": "ok"}'
    assert created["max_retries"] == 0

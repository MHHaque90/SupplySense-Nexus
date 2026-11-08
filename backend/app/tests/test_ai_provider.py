"""Phase 11 LLM provider tests (C3, C7): Mock, httpx transport, gating."""

import json

import httpx
import pytest

from backend.app.ai.intents import classify, select_tools
from backend.app.core.config import settings
from backend.app.core.errors import APIError, ErrorCode
from backend.app.integration import llm_provider
from backend.app.integration.llm_provider import (
    LLMMessage,
    LLMRequest,
    HttpOpenAIProvider,
    MockProvider,
    ProviderConfigurationError,
    build_provider,
    get_llm_provider,
    reset_provider_cache,
)

MESSAGES = [LLMMessage(role="user", content="How is inventory health for warehouse 1?")]


@pytest.fixture(autouse=True)
def _clean_provider_cache():
    reset_provider_cache()
    yield
    reset_provider_cache()


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_plan():
    provider = MockProvider()
    response = await provider.complete(LLMRequest(messages=MESSAGES, model="any"))
    plan = json.loads(response.text)
    intent, confidence = classify(MESSAGES[0].content)
    assert plan["intent"] == intent
    assert plan["confidence"] == confidence
    expected_tools = list(select_tools(intent, MESSAGES[0].content))
    assert [c["tool"] for c in plan["tool_calls"]] == expected_tools
    assert set(plan) == {"intent", "tool_calls", "response", "confidence"}
    assert response.provider == "mock"
    described = provider.describe()
    assert described["mode"] == "offline-mock"
    assert described["network"] is False


@pytest.mark.asyncio
async def test_mock_provider_tool_results_synthesis_echoes_scalars():
    payload = json.dumps(
        [
            {
                "tool": "get_inventory_position",
                "data_source_label": "synthetic",
                "data": {"on_hand": 42, "sku": "SKU-1"},
            }
        ]
    )
    provider = MockProvider()
    response = await provider.complete(
        LLMRequest(
            messages=[LLMMessage(role="user", content=f"TOOL_RESULTS: {payload}")],
            model="any",
        )
    )
    plan = json.loads(response.text)
    assert plan["tool_calls"] == []
    assert "get_inventory_position" in plan["response"]
    assert "on_hand=42" in plan["response"]
    assert "synthetic" in plan["response"]
    assert plan["confidence"] == 0.70


def test_provider_construction_rejects_empty_key():
    with pytest.raises(ProviderConfigurationError):
        HttpOpenAIProvider(api_key="", model="m")


def test_build_provider_defaults_to_mock_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AI_ASSISTANT", False)
    provider = build_provider()
    assert isinstance(provider, MockProvider)


def test_build_provider_rejects_unknown_name(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AI_ASSISTANT", True)
    monkeypatch.setattr(settings, "AI_PROVIDER", "mystery-model")
    with pytest.raises(ProviderConfigurationError):
        build_provider()


def test_build_provider_rejects_openai_with_empty_key(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AI_ASSISTANT", True)
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ProviderConfigurationError):
        build_provider()


def test_get_llm_provider_misconfig_becomes_503(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AI_ASSISTANT", True)
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(APIError) as excinfo:
        get_llm_provider()
    assert excinfo.value.code == ErrorCode.AI_UNAVAILABLE
    assert excinfo.value.status_code == 503


def _transport_with(responses):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return httpx.MockTransport(handler), calls


def _ok_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "model": "gpt-4o-mini",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.mark.asyncio
async def test_openai_provider_success_over_httpx():
    transport, calls = _transport_with([httpx.Response(200, json=_ok_body('{"intent": "general_inquiry"}'))])
    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890", model="gpt-4o-mini", transport=transport
    )
    response = await provider.complete(LLMRequest(messages=MESSAGES, model="gpt-4o-mini"))
    assert response.text == '{"intent": "general_inquiry"}'
    assert response.provider == "openai"
    assert response.input_tokens == 10
    assert len(calls) == 1
    assert calls[0].headers["authorization"] == "Bearer sk-test-key-1234567890"
    await provider.aclose()


@pytest.mark.asyncio
async def test_openai_provider_retries_transient_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm_provider, "RETRY_BACKOFF_SECONDS", 0.01)
    transport, calls = _transport_with(
        [
            httpx.Response(429, json={"error": "slow down"}),
            httpx.Response(200, json=_ok_body("ok")),
        ]
    )
    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890", model="m", transport=transport
    )
    response = await provider.complete(LLMRequest(messages=MESSAGES, model="m"))
    assert response.text == "ok"
    assert len(calls) == 2
    await provider.aclose()


@pytest.mark.asyncio
async def test_openai_provider_bounded_retries_then_503(monkeypatch):
    monkeypatch.setattr(llm_provider, "RETRY_BACKOFF_SECONDS", 0.01)
    transport, calls = _transport_with([httpx.Response(500, json={})])
    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890", model="m", transport=transport
    )
    with pytest.raises(APIError) as excinfo:
        await provider.complete(LLMRequest(messages=MESSAGES, model="m"))
    assert excinfo.value.code == ErrorCode.AI_UNAVAILABLE
    assert len(calls) == llm_provider.MAX_RETRIES + 1
    await provider.aclose()


@pytest.mark.asyncio
async def test_openai_provider_non_retryable_400_fails_fast():
    transport, calls = _transport_with([httpx.Response(400, json={})])
    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890", model="m", transport=transport
    )
    with pytest.raises(APIError) as excinfo:
        await provider.complete(LLMRequest(messages=MESSAGES, model="m"))
    assert excinfo.value.code == ErrorCode.AI_UNAVAILABLE
    assert len(calls) == 1
    await provider.aclose()


@pytest.mark.asyncio
async def test_openai_provider_malformed_body_503():
    transport, _ = _transport_with([httpx.Response(200, json={"nope": True})])
    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890", model="m", transport=transport
    )
    with pytest.raises(APIError) as excinfo:
        await provider.complete(LLMRequest(messages=MESSAGES, model="m"))
    assert excinfo.value.code == ErrorCode.AI_UNAVAILABLE
    await provider.aclose()


@pytest.mark.asyncio
async def test_openai_provider_transport_failure_bounded(monkeypatch):
    monkeypatch.setattr(llm_provider, "RETRY_BACKOFF_SECONDS", 0.01)
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectError("boom", request=request)

    provider = HttpOpenAIProvider(
        api_key="sk-test-key-1234567890",
        model="m",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIError) as excinfo:
        await provider.complete(LLMRequest(messages=MESSAGES, model="m"))
    assert excinfo.value.code == ErrorCode.AI_UNAVAILABLE
    assert attempts["count"] == llm_provider.MAX_RETRIES + 1
    await provider.aclose()


def test_cloud_describe_never_exposes_key():
    provider = HttpOpenAIProvider(api_key="sk-super-secret-key-12345", model="m")
    described = provider.describe()
    assert "sk-super-secret-key-12345" not in json.dumps(described)
    assert described["mode"] == "cloud"
    assert described["network"] is True

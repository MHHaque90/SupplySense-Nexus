"""LLM provider abstraction (Phase 11): MockProvider-first, httpx-only.

Decisions enforced here:

- **C3**: offline MockProvider is the default and keeps chat fully
  functional with zero network access; it produces structured plans from
  the deterministic classifier in :mod:`backend.app.ai.intents`.
- **C7**: the only cloud transport is :class:`HttpOpenAIProvider` built on
  ``httpx``. No OpenAI/Google SDK, no tenacity, no ambient packages.
- Feature gate: ``ENABLE_AI_ASSISTANT=false`` -> MockProvider;
  ``true`` -> cloud provider validated at construction (empty key or
  unsupported provider raises :class:`ProviderConfigurationError`, surfaced
  as 503 ``AI_UNAVAILABLE``). No silent fallback from cloud to Mock.
- Bounded retries: transient transport failures/429/5xx only, maximum
  ``MAX_RETRIES`` additional attempts, fixed backoff, then AI_UNAVAILABLE.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from backend.app.ai.intents import classify, select_tools
from backend.app.core.config import settings
from backend.app.core.errors import APIError, ErrorCode

logger = logging.getLogger("supplysense.ai.provider")

OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.5
MOCK_MODEL = "mock-rule-based-v1"


class ProviderConfigurationError(RuntimeError):
    """Cloud provider requested but not usable (empty key / unknown name)."""


@dataclass(frozen=True)
class LLMMessage:
    """One chat message passed to a provider."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """Provider-agnostic completion request (JSON-plan contract)."""

    messages: list[LLMMessage]
    model: str
    temperature: float = 0.0
    max_tokens: int = 1200
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Provider-agnostic completion response (``text`` is the JSON plan)."""

    text: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Structural interface every provider implements."""

    def describe(self) -> dict[str, Any]:
        """Return non-sensitive provider metadata for audit/meta logging."""
        ...

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return one completion; raise APIError(AI_UNAVAILABLE) on failure."""
        ...


def _last_user_text(request: LLMRequest) -> str:
    """Return the content of the final user message."""
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content
    return ""


def _extract_marker(message: str) -> tuple[str, str] | None:
    """Split a ``<MARKER> payload`` prompt marker into ``(marker, payload)``."""
    match = re.match(r"^([A-Z_]+):\s(.*)$", message.strip(), re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None


class MockProvider:
    """Deterministic offline provider (no network, no model weights).

    Round contract mirrors the cloud provider: the response ``text`` is a
    JSON plan ``{"intent", "tool_calls", "response", "confidence"}``. All
    values are fixed heuristics and labeled as such in limitations; no
    analytical result is ever invented (tool results are the only source of
    numbers).
    """

    provider_name = "mock"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a deterministic JSON plan for the latest prompt."""
        started = time.perf_counter()
        text = _last_user_text(request)
        plan = self._plan(text, request)
        return LLMResponse(
            text=json.dumps(plan, default=str),
            provider=self.provider_name,
            model=MOCK_MODEL,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def _plan(self, text: str, request: LLMRequest) -> dict[str, Any]:
        marker = _extract_marker(text)
        if marker and marker[0] == "TOOL_RESULTS":
            return self._synthesis_plan(marker[1])
        if marker and marker[0] == "PLAN":
            text = marker[1]
        intent, confidence = classify(text)
        tool_calls = [
            {"tool": name, "parameters": {}}
            for name in select_tools(intent, text)
        ]
        if tool_calls:
            response = (
                "I will retrieve the supporting data for this request. "
                "All values will be labeled with their data source."
            )
        else:
            response = (
                "This request needs no new computation. Ask about forecasts, "
                "inventory health, supplier delivery, data quality, or run a "
                "simulated scenario or optimization analysis for evidence."
            )
        return {
            "intent": intent,
            "tool_calls": tool_calls,
            "response": response,
            "confidence": confidence,
        }

    def _synthesis_plan(self, payload: str) -> dict[str, Any]:
        """Compose an honest summary by echoing retrieved tool scalars."""
        try:
            results = json.loads(payload)
        except (TypeError, ValueError):
            results = []
        lines: list[str] = []
        labels: set[str] = set()
        if isinstance(results, list):
            for entry in results:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("tool", "tool"))
                label = str(entry.get("data_source_label", "synthetic"))
                labels.add(label)
                data = entry.get("data")
                scalars = _top_scalars(data) if isinstance(data, dict) else []
                detail = "; ".join(scalars[:6]) if scalars else "no scalar values in result"
                lines.append(f"{name} (label: {label}): {detail}")
        body = " | ".join(lines) if lines else "no tool results were returned"
        return {
            "intent": None,
            "tool_calls": [],
            "response": (
                "Retrieved evidence follows (values echoed from tool results; "
                f"data labels: {', '.join(sorted(labels)) or 'synthetic'}). {body}"
            ),
            "confidence": 0.70,
        }

    def describe(self) -> dict[str, Any]:
        """Return non-sensitive provider metadata."""
        return {
            "provider": self.provider_name,
            "model": MOCK_MODEL,
            "mode": "offline-mock",
            "network": False,
        }


def _top_scalars(data: dict[str, Any], limit: int = 6) -> list[str]:
    """Flatten up to ``limit`` scalar key/value pairs (deterministic order)."""
    out: list[str] = []
    for key in sorted(data.keys()):
        value = data[key]
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float, str)):
            out.append(f"{key}={value}")
        if len(out) >= limit:
            break
    return out


class HttpOpenAIProvider:
    """OpenAI-compatible chat-completions transport over httpx only."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float | None = None,
        base_url: str = OPENAI_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is empty.")
        self._api_key = api_key
        self.model = model
        timeout = timeout_seconds or settings.AI_REQUEST_TIMEOUT_SECONDS
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """POST one chat-completions call with bounded transient retries."""
        payload = {
            "model": request.model or self.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
        }
        started = time.perf_counter()
        response = await self._post_with_retries(payload)
        if response.status_code >= 400:
            logger.error(
                "openai provider HTTP %s (request id: %s)",
                response.status_code,
                response.headers.get("x-request-id", "unknown"),
            )
            raise APIError(
                ErrorCode.AI_UNAVAILABLE,
                ErrorCode.message_for(ErrorCode.AI_UNAVAILABLE),
            )
        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.error("openai provider malformed response: %s", type(exc).__name__)
            raise APIError(
                ErrorCode.AI_UNAVAILABLE,
                ErrorCode.message_for(ErrorCode.AI_UNAVAILABLE),
            ) from exc
        usage = body.get("usage") or {}
        return LLMResponse(
            text=text or "",
            provider=self.provider_name,
            model=str(body.get("model", request.model or self.model)),
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def _post_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        """Retry transient failures only (429/5xx/transport), bounded."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                logger.warning(
                    "openai transport failure (attempt %s/%s): %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    type(exc).__name__,
                )
                if attempt >= MAX_RETRIES:
                    raise APIError(
                        ErrorCode.AI_UNAVAILABLE,
                        ErrorCode.message_for(ErrorCode.AI_UNAVAILABLE),
                    ) from exc
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < MAX_RETRIES:
                retry_after = response.headers.get("retry-after")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.replace(".", "", 1).isdigit()
                    else RETRY_BACKOFF_SECONDS * (attempt + 1)
                )
                await asyncio.sleep(min(delay, 5.0))
                continue
            return response
        raise APIError(
            ErrorCode.AI_UNAVAILABLE,
            ErrorCode.message_for(ErrorCode.AI_UNAVAILABLE),
        )

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    def describe(self) -> dict[str, Any]:
        """Return non-sensitive provider metadata (never the key)."""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "mode": "cloud",
            "network": True,
        }


_cached_provider: LLMProvider | None = None


def build_provider() -> LLMProvider:
    """Build the provider implied by settings; raises when misconfigured."""
    if not settings.ENABLE_AI_ASSISTANT:
        return MockProvider()
    name = settings.AI_PROVIDER.strip().lower()
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return HttpOpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.AI_MODEL,
            timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )
    raise ProviderConfigurationError(f"Unsupported AI_PROVIDER: {name!r}.")


def get_llm_provider() -> LLMProvider:
    """Cached provider resolver (FastAPI dependency; overridable in tests)."""
    global _cached_provider
    if _cached_provider is None:
        try:
            _cached_provider = build_provider()
        except ProviderConfigurationError as exc:
            raise APIError(ErrorCode.AI_UNAVAILABLE) from exc
    return _cached_provider


def reset_provider_cache() -> None:
    """Drop the cached provider (settings changes or tests)."""
    global _cached_provider
    _cached_provider = None


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "HttpOpenAIProvider",
    "MockProvider",
    "ProviderConfigurationError",
    "build_provider",
    "get_llm_provider",
    "reset_provider_cache",
]

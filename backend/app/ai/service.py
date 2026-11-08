"""AI Decision Copilot service: orchestrates one chat turn end to end.

Turn pipeline (bounded at every stage):

1. Rate-limit check (fail-open limiter, 429 with ``Retry-After``).
2. Input guardrail check (refusals are persisted and audited, not silent).
3. Conversation resolve/create + bounded history load (PostgreSQL, C4).
4. Provider round 1 -> JSON plan (intent + tool calls); invalid JSON falls
   back deterministically (never guessed).
5. Tool execution via the registry/executor (org-scoped, audited, capped at
   ``settings.AI_MAX_TOOL_CALLS_PER_TURN``).
6. Provider round 2 over tool results -> final wording (max 2 rounds).
7. Output guardrails (governance wording, redaction, bounds).
8. Evidence/limitations/confidence assembly (labels from tool provenance).
9. Persist assistant message, audit ``ai.chat``, commit.

Nothing in this module mutates business data; declared actions only create
approval records (see :mod:`backend.app.ai.approvals`).
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai import approvals as approval_service
from backend.app.ai import audit, guardrails, memory, prompts
from backend.app.ai.executor import execute_tool
from backend.app.ai.intents import Intent, classify
from backend.app.ai.ratelimit import RateLimiter, enforce_rate_limit
from backend.app.ai.registry import ToolContext, ToolRegistry
from backend.app.ai.responses import AIChatResponse, Evidence
from backend.app.core.config import settings
from backend.app.core.data_labels import DataSourceLabel
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext
from backend.app.integration.llm_provider import LLMMessage, LLMProvider, LLMRequest
from backend.app.models.ai import AiConversation, MessageRole

logger = logging.getLogger("supplysense.ai.service")

MAX_PROVIDER_ROUNDS = 2
CONVERSATION_LABEL = "user-provided"
ASSISTANT_LABEL = "derived"


def _parse_plan(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from provider text (fence-tolerant)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start : end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _clamp_confidence(value: Any, default: float) -> float:
    """Coerce provider confidence into ``[0, 1]`` with a safe default."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def _synthesis_fallback(results: list[dict[str, Any]]) -> str:
    """Deterministic evidence summary used when round 2 is unparseable."""
    lines = []
    for entry in results:
        data = entry.get("data")
        scalars = []
        if isinstance(data, dict):
            for key in sorted(data)[:6]:
                value = data[key]
                if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                    scalars.append(f"{key}={value}")
        detail = "; ".join(scalars) if scalars else "structured result (see evidence)"
        lines.append(
            f"{entry.get('tool', 'tool')} (label: {entry.get('label', 'synthetic')}): "
            f"{detail}"
        )
    return (
        "Evidence retrieved (values echoed from tool results): "
        + " | ".join(lines)
        if lines
        else "No tool evidence was available for this turn."
    )


async def _resolve_conversation(
    session: AsyncSession,
    auth: AuthContext,
    conversation_id: str | None,
    session_id: str | None,
    title_hint: str | None = None,
) -> tuple[AiConversation, str | None]:
    """Load an owned conversation or create a new one (flushed for reads)."""
    if conversation_id:
        loaded = (
            await session.execute(
                select(AiConversation)
                .where(AiConversation.id == conversation_id)
                .where(AiConversation.user_id == auth.user_id)
                .where(AiConversation.organization_id == auth.organization_id)
            )
        ).scalar_one_or_none()
        if loaded is None:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Conversation {conversation_id!r} was not found.",
            )
        return loaded, loaded.session_id or session_id
    conversation = AiConversation(
        organization_id=auth.organization_id,
        user_id=auth.user_id,
        session_id=session_id,
        title=(title_hint or "")[:80] or None,
        data_source_label=CONVERSATION_LABEL,
    )
    session.add(conversation)
    await session.flush()
    return conversation, session_id


async def _complete_plan(
    provider: LLMProvider,
    messages: list[LLMMessage],
    fallback: dict[str, Any],
) -> tuple[dict[str, Any], str, str | None]:
    """Run one provider round; returns ``(plan, raw_text, fallback_note)``."""
    response = await provider.complete(
        LLMRequest(messages=messages, model=settings.AI_MODEL)
    )
    plan = _parse_plan(response.text)
    if plan is None:
        logger.warning("provider returned unparseable plan (provider=%s)", response.provider)
        return fallback, response.text, (
            "Provider output was not valid JSON; a deterministic fallback "
            "answer was used instead."
        )
    return plan, response.text, None


def _build_evidence(results: list[dict[str, Any]]) -> list[Evidence]:
    """Convert successful tool results into labeled Evidence entries."""
    timestamp = datetime.now(UTC).isoformat()
    evidence: list[Evidence] = []
    for entry in results:
        label = str(entry.get("label", "synthetic"))
        if label not in DataSourceLabel.values():
            label = "synthetic"
        when = str(entry.get("analysis_date") or timestamp)
        evidence.append(
            Evidence(
                source=str(entry.get("source", entry.get("tool", "tool"))),
                label=label,
                timestamp=when,
                confidence=None,
                limitations=list(entry.get("limitations", [])),
            )
        )
    return evidence


def _provider_limitations(provider: LLMProvider) -> list[str]:
    """Standing limitations implied by the active provider mode."""
    described = provider.describe()
    if described.get("mode") == "offline-mock":
        return [
            "Offline mock provider: intent and confidence values are fixed "
            "heuristics, not calibrated model outputs.",
        ]
    return [
        f"Cloud provider wording (model {described.get('model', 'unknown')}) "
        "is generated text; only tool-evidenced values are factual."
    ]


async def run_chat(
    session: AsyncSession,
    auth: AuthContext,
    message: str,
    conversation_id: str | None,
    session_id: str | None,
    provider: LLMProvider,
    registry: ToolRegistry,
    limiter: RateLimiter,
) -> dict[str, Any]:
    """Execute one chat turn and return ``{"data", "meta"}`` for the route.

    Raises 429 (rate limit), 404 (foreign/unknown conversation), 503
    (provider unavailable). All other failures are converted into an
    in-band assistant answer with explicit limitations.
    """
    await enforce_rate_limit(session, auth, limiter, session_id)

    conversation, effective_session_id = await _resolve_conversation(
        session, auth, conversation_id, session_id, title_hint=message
    )
    history = await memory.load_history(
        session, conversation.id, auth.user_id, auth.organization_id
    )
    await memory.append_message(
        session,
        conversation.id,
        MessageRole.USER,
        message,
        data_source_label=CONVERSATION_LABEL,
    )
    await session.flush()

    limitations: list[str] = list(_provider_limitations(provider))
    verdict = guardrails.check_input(message)
    if verdict.blocked:
        outcome = await _finalize(
            session=session,
            auth=auth,
            conversation=conversation,
            session_id=effective_session_id,
            response_text=guardrails.REFUSAL_RESPONSE,
            confidence=0.10,
            evidence=[],
            limitations=limitations + [str(verdict.reason), "Input guardrail refusal."],
            intent=Intent.GENERAL_INQUIRY.value,
            tool_calls=[],
            approved=True,
            provider=provider,
            guardrail_blocked=True,
        )
        return outcome

    fallback_intent, _ = classify(message)
    plan_fallback = {
        "intent": fallback_intent,
        "tool_calls": [],
        "response": (
            "I could not produce a structured plan for that request. Please "
            "rephrase it around forecasts, inventory, suppliers, data "
            "quality, simulated scenarios, replays, or optimization."
        ),
        "confidence": 0.30,
    }
    plan, plan_text, round1_note = await _complete_plan(
        provider, prompts.plan_messages(history, message), plan_fallback
    )
    if round1_note:
        limitations.append(round1_note)

    intent = str(plan.get("intent") or fallback_intent)
    if intent not in Intent.values():
        intent = fallback_intent
    confidence = _clamp_confidence(plan.get("confidence"), 0.5)

    raw_calls = plan.get("tool_calls") or []
    tool_calls: list[dict[str, Any]] = []
    if isinstance(raw_calls, list):
        for entry in raw_calls[: settings.AI_MAX_TOOL_CALLS_PER_TURN]:
            if isinstance(entry, dict) and isinstance(entry.get("tool"), str):
                tool_calls.append(
                    {
                        "tool": str(entry["tool"]),
                        "parameters": dict(entry.get("parameters") or {})
                        if isinstance(entry.get("parameters"), dict)
                        else {},
                    }
                )

    results: list[dict[str, Any]] = []
    approval_ids: list[str] = []
    for call in tool_calls:
        context = ToolContext(
            session=session,
            auth=auth,
            params=call["parameters"],
            conversation_id=conversation.id,
            session_id=effective_session_id,
        )
        result = await execute_tool(
            registry, call["tool"], call["parameters"], context
        )
        results.append(result)
        if result["status"] == "error":
            code = (result.get("error") or {}).get("code")
            spec = None
            try:
                spec = registry.get(call["tool"])
            except APIError:
                limitations.append(
                    f"Tool {call['tool']!r} is not registered and was skipped."
                )
            if spec is not None and spec.requires_approval:
                approval = await approval_service.create_approval(
                    session,
                    auth=auth,
                    conversation_id=conversation.id,
                    action=spec.name,
                    declaration={
                        "tool": spec.name,
                        "description": spec.description,
                        "parameters": call["parameters"],
                        "status": "awaiting_human_decision",
                    },
                )
                approval_ids.append(approval.id)
                limitations.append(
                    f"Declared action {spec.name!r} was recorded as approval "
                    f"{approval.id}; no action was executed (approvals never "
                    "execute)."
                )
            elif code is not None:
                message_text = (result.get("error") or {}).get("message", "")
                limitations.append(f"Tool {call['tool']!r}: {message_text}")

    ok_results = [entry for entry in results if entry.get("status") == "ok"]
    final_text = str(plan.get("response") or "")
    if ok_results:
        synthesis_fallback = _synthesis_fallback(ok_results)
        plan2_fallback = {
            "intent": intent,
            "tool_calls": [],
            "response": synthesis_fallback,
            "confidence": min(confidence, 0.65),
        }
        messages = prompts.tool_results_messages(
            history, message, plan_text, ok_results
        )
        plan2, _, round2_note = await _complete_plan(
            provider, messages, plan2_fallback
        )
        if round2_note:
            limitations.append(round2_note)
        final_text = str(plan2.get("response") or synthesis_fallback)
        confidence = _clamp_confidence(
            plan2.get("confidence"), min(confidence, 0.65)
        )
    elif tool_calls:
        final_text = final_text or (
            "The requested tools did not return usable evidence; see the "
            "limitations for each failure."
        )

    if not final_text:
        final_text = (
            "No answer text was produced for this turn; please rephrase."
        )

    scrubbed = guardrails.sanitize_output(final_text)
    limitations.extend(scrubbed.notes)
    evidence = _build_evidence(ok_results)
    if not evidence:
        confidence = min(confidence, 0.5)
        limitations.append(
            "No tool evidence was attached; the answer is not data-backed."
        )
    if len(results) > len(ok_results) and not approval_ids:
        limitations.append(
            f"{len(results) - len(ok_results)} tool call(s) returned errors."
        )

    outcome = await _finalize(
        session=session,
        auth=auth,
        conversation=conversation,
        session_id=effective_session_id,
        response_text=scrubbed.text,
        confidence=confidence,
        evidence=evidence,
        limitations=limitations,
        intent=intent,
        tool_calls=results,
        approved=not approval_ids,
        provider=provider,
        guardrail_blocked=False,
    )
    outcome["meta"]["approval_ids"] = approval_ids
    return outcome


async def _finalize(
    *,
    session: AsyncSession,
    auth: AuthContext,
    conversation: AiConversation,
    session_id: str | None,
    response_text: str,
    confidence: float,
    evidence: list[Evidence],
    limitations: list[str],
    intent: str,
    tool_calls: list[dict[str, Any]],
    approved: bool,
    provider: LLMProvider,
    guardrail_blocked: bool,
) -> dict[str, Any]:
    """Persist the assistant turn, audit it, and build the response payload."""
    described = provider.describe()
    payload = AIChatResponse(
        response=response_text,
        confidence=max(0.0, min(1.0, confidence)),
        evidence=evidence,
        limitations=limitations,
        approved=approved,
    )
    await memory.append_message(
        session,
        conversation.id,
        MessageRole.ASSISTANT,
        response_text,
        intent=intent,
        confidence=payload.confidence,
        tool_calls=[
            {
                "tool": entry.get("tool"),
                "status": entry.get("status"),
                "error": entry.get("error"),
            }
            for entry in tool_calls
        ],
        provider=str(described.get("provider", "unknown")),
        model=str(described.get("model", "unknown")),
        data_source_label=ASSISTANT_LABEL,
    )
    conversation.last_intent = intent
    await audit.record(
        session,
        action=audit.CHAT,
        user_id=auth.user_id,
        entity_type="ai_conversation",
        entity_id=conversation.id,
        session_id=session_id,
        parameters={
            "intent": intent,
            "confidence": payload.confidence,
            "tools": [entry.get("tool") for entry in tool_calls],
            "tool_errors": [
                entry.get("tool") for entry in tool_calls
                if entry.get("status") == "error"
            ],
            "provider": described.get("provider"),
            "approved": approved,
            "guardrail_blocked": guardrail_blocked,
            "evidence_count": len(evidence),
        },
    )
    await session.flush()
    return {
        "data": payload.model_dump(),
        "meta": {
            "conversation_id": conversation.id,
            "session_id": session_id,
            "intent": intent,
            "provider": described.get("provider"),
        },
    }


__all__ = ["MAX_PROVIDER_ROUNDS", "run_chat"]

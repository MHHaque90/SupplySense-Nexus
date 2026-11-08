"""Audit writes for AI Decision Copilot operations (Phase 11).

Append-only writes into the existing ``audit_events`` table (write-once:
rows are added, never updated or deleted). ``user_id`` is required by the
governance schema, so unauthenticated failures are recorded only in the
application log — never fabricated into the audit trail.

Logged actions:

- ``ai.chat`` — one row per chat request (intent, tools, confidence,
  provider, conversation).
- ``ai.tool.call`` — one row per executed (or refused) tool call.
- ``ai.approval.decision`` — one row per approve/reject decision.
- ``ai.ratelimit.exceeded`` — one row per denied request.

Parameters are JSON text, bounded in size, and never contain raw API keys
or provider secrets.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AuditEvent

logger = logging.getLogger("supplysense.ai.audit")

MAX_PARAMETERS_CHARS = 4000

CHAT = "ai.chat"
TOOL_CALL = "ai.tool.call"
APPROVAL_DECISION = "ai.approval.decision"
RATE_LIMIT_EXCEEDED = "ai.ratelimit.exceeded"


def _bounded_json(parameters: dict[str, Any] | None) -> str | None:
    """Serialize parameters as compact JSON, truncated to a safe size."""
    if parameters is None:
        return None
    text = json.dumps(parameters, default=str, sort_keys=True)
    if len(text) > MAX_PARAMETERS_CHARS:
        text = json.dumps(
            {"truncated": True, "preview": text[: MAX_PARAMETERS_CHARS - 64]},
            default=str,
        )
    return text


async def record(
    session: AsyncSession,
    *,
    action: str,
    user_id: str,
    entity_type: str,
    entity_id: str | None = None,
    session_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one audit event (no commit: joins the caller's transaction)."""
    event = AuditEvent(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        parameters=_bounded_json(parameters),
        timestamp=datetime.now(UTC).date(),
        session_id=session_id,
    )
    session.add(event)
    logger.info(
        "audit action=%s entity=%s user=%s conversation=%s",
        action,
        entity_type,
        user_id,
        entity_id,
    )
    return event


__all__ = [
    "APPROVAL_DECISION",
    "CHAT",
    "MAX_PARAMETERS_CHARS",
    "RATE_LIMIT_EXCEEDED",
    "TOOL_CALL",
    "record",
]

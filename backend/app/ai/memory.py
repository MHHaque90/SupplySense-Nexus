"""Bounded PostgreSQL-backed conversation memory (Phase 11, decision C4).

Rules:

- History lives in ``ai_conversations`` / ``ai_messages`` (no in-memory-only
  store, no vector database, no hidden summarization model).
- Only the most recent ``settings.AI_MAX_HISTORY_MESSAGES`` messages are
  fed to the provider; when older turns exist they are replaced by one
  explicit marker so truncation is visible, never silent.
- A conversation is strictly single-organization and single-user: rows are
  read with both scopes applied, never by id alone.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.ai import AiConversation, AiMessage, MessageRole

HISTORY_OMITTED_MARKER = (
    "[earlier turns omitted: history is bounded to the most recent "
    f"{settings.AI_MAX_HISTORY_MESSAGES} messages]"
)


async def next_sequence(session: AsyncSession, conversation_id: str) -> int:
    """Return the next monotonically increasing sequence for a conversation."""
    current = (
        await session.execute(
            select(AiMessage.sequence)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return 0 if current is None else int(current) + 1


async def append_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    *,
    intent: str | None = None,
    confidence: float | None = None,
    tool_calls: list[dict] | None = None,
    provider: str | None = None,
    model: str | None = None,
    data_source_label: str = "user-provided",
) -> AiMessage:
    """Persist one message with a fresh sequence number (write-once)."""
    sequence = await next_sequence(session, conversation_id)
    message = AiMessage(
        conversation_id=conversation_id,
        role=role,
        sequence=sequence,
        content=content,
        intent=intent,
        confidence=confidence,
        tool_calls=tool_calls,
        provider=provider,
        model=model,
        data_source_label=data_source_label,
    )
    session.add(message)
    return message


async def load_history(
    session: AsyncSession,
    conversation_id: str,
    user_id: str,
    organization_id: str,
) -> list[dict[str, str]]:
    """Return bounded provider history for one scoped conversation.

    Returns the most recent ``settings.AI_MAX_HISTORY_MESSAGES`` user and
    assistant turns, oldest first. When truncation occurred, the oldest
    returned entry is replaced by :data:`HISTORY_OMITTED_MARKER` so the
    provider (and any reader) sees the omission explicitly.
    """
    conversation = (
        await session.execute(
            select(AiConversation)
            .where(AiConversation.id == conversation_id)
            .where(AiConversation.user_id == user_id)
            .where(AiConversation.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if conversation is None:
        return []
    limit = settings.AI_MAX_HISTORY_MESSAGES
    total = (
        await session.execute(
            select(func.count(AiMessage.id)).where(
                AiMessage.conversation_id == conversation_id
            )
        )
    ).scalar_one_or_none() or 0
    rows = (
        await session.execute(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation_id)
            .order_by(AiMessage.sequence.desc())
            .limit(limit)
        )
    ).scalars().all()
    history = [
        {"role": row.role, "content": row.content}
        for row in reversed(rows)
        if row.role in (MessageRole.USER, MessageRole.ASSISTANT)
    ]
    if history and int(total) > limit:
        history[0] = {"role": "user", "content": HISTORY_OMITTED_MARKER}
    return history


__all__ = [
    "HISTORY_OMITTED_MARKER",
    "append_message",
    "load_history",
    "next_sequence",
]

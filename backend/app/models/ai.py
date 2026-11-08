"""AI Decision Copilot models (Phase 11): conversations, messages, approvals.

Every table carries ``data_source_label`` per the data-labeling rules.
User-authored rows are labeled ``user-provided``; assistant rows are
``derived`` from platform data; approval records are ``derived``.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin

#: JSON payload column type: JSONB on PostgreSQL (matches the migration),
#: generic JSON elsewhere (SQLite-based tooling, offline checks).
AiJson = JSON().with_variant(postgresql.JSONB(), "postgresql")


class ApprovalStatus:
    """Allowed values for :attr:`AiApproval.status`."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid approval status values."""
        return [cls.PENDING, cls.APPROVED, cls.REJECTED]


class MessageRole:
    """Allowed values for :attr:`AiMessage.role`."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid message role values."""
        return [cls.USER, cls.ASSISTANT, cls.TOOL]


class AiConversation(BaseMixin, DataProvenanceMixin, Base):
    """One authenticated chat conversation belonging to one organization."""

    __tablename__ = "ai_conversations"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        """Return a non-sensitive representation (ids only)."""
        return f"AiConversation(id={self.id}, organization_id={self.organization_id})"


class AiMessage(BaseMixin, DataProvenanceMixin, Base):
    """One bounded conversation turn stored verbatim for auditability."""

    __tablename__ = "ai_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(AiJson, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        """Return a non-sensitive representation (ids only)."""
        return f"AiMessage(id={self.id}, role={self.role}, sequence={self.sequence})"


class AiApproval(BaseMixin, DataProvenanceMixin, Base):
    """A declared action awaiting an explicit human approve/reject decision.

    Approval records are declarative only: approving one never executes an
    action. No code path exists that mutates business data from an approval.
    """

    __tablename__ = "ai_approvals"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_conversations.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    declaration: Mapped[dict[str, Any]] = mapped_column(AiJson, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApprovalStatus.PENDING, index=True
    )
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        """Return a non-sensitive representation (ids only)."""
        return f"AiApproval(id={self.id}, action={self.action}, status={self.status})"


__all__ = [
    "AiApproval",
    "AiConversation",
    "AiMessage",
    "ApprovalStatus",
    "MessageRole",
]

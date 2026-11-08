"""Pydantic request/response schemas for the AI Decision Copilot API.

The response contract fixed by the Phase 11 audit:

- ``AIChatResponse`` = ``{response, confidence, evidence[], limitations[],
  approved}`` (exactly these five fields).
- ``Evidence`` = ``{source, label, timestamp, confidence?, limitations}``.
- Labels must be members of :class:`DataSourceLabel` (never free text).
- ``approved`` is ``False`` whenever the reply carries a declared action
  awaiting a human decision; it is ``True`` for purely informational
  answers (nothing pending).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.data_labels import DataSourceLabel


class Evidence(BaseModel):
    """One provenance-stamped fact backing an assistant answer."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=255)
    label: str
    timestamp: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("label")
    @classmethod
    def _valid_label(cls, value: str) -> str:
        if value not in DataSourceLabel.values():
            raise ValueError(f"invalid data source label: {value!r}")
        return value


class AIChatResponse(BaseModel):
    """Success payload for ``POST /ai/chat`` (five fields, contract-locked)."""

    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    approved: bool


class ChatRequest(BaseModel):
    """Request body for ``POST /ai/chat`` (identity comes only from auth)."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=36)
    session_id: str | None = Field(default=None, max_length=100)


class ToolSummary(BaseModel):
    """One entry of ``GET /ai/tools``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    category: str
    parameters: dict[str, Any]
    executable: bool
    requires_approval: bool


class ApprovalRequest(BaseModel):
    """Request body for ``POST /ai/approval`` (manager+ role)."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1, max_length=36)
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=2000)


class ApprovalView(BaseModel):
    """Success payload for ``POST /ai/approval`` (status only, no execution)."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    action: str
    status: str
    decided_at: str | None = None
    executed: bool = False


__all__ = [
    "AIChatResponse",
    "ApprovalRequest",
    "ApprovalView",
    "ChatRequest",
    "Evidence",
    "ToolSummary",
]

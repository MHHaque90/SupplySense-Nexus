"""AI Decision Copilot endpoints (Phase 11) under ``/api/v1/ai/*``.

- ``POST /ai/chat``  — analyst+ — one bounded chat turn (MockProvider by
  default; cloud provider when ``ENABLE_AI_ASSISTANT=true``).
- ``GET  /ai/tools`` — analyst+ — the tool registry listing (executable
  tools plus approval-required declarations).
- ``POST /ai/approval`` — manager+ — record a human approve/reject decision
  on a declared action; **never executes anything**.

All three endpoints enforce per-user rate limits (429 ``RATE_LIMIT_EXCEEDED``
with ``Retry-After``). Identity comes exclusively from the Bearer API key;
the request body never carries identity. Health endpoints stay public.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai import approvals as approval_service
from backend.app.ai import service
from backend.app.ai.ratelimit import RateLimiter, enforce_rate_limit, get_rate_limiter
from backend.app.ai.registry import ToolRegistry, get_tool_registry
from backend.app.ai.responses import (
    ApprovalRequest,
    ApprovalView,
    ChatRequest,
    ToolSummary,
)
from backend.app.core.database import get_db
from backend.app.core.errors import success_envelope
from backend.app.core.security import AuthContext, require_roles
from backend.app.integration.llm_provider import LLMProvider, get_llm_provider

router = APIRouter()

ANALYST = "analyst"
PLANNER = "planner"
MANAGER = "manager"
EXECUTIVE = "executive"

ANALYST_PLUS = (ANALYST, PLANNER, MANAGER, EXECUTIVE)
MANAGER_PLUS = (MANAGER, EXECUTIVE)


@router.post("/ai/chat")
async def ai_chat(
    body: ChatRequest,
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
    registry: ToolRegistry = Depends(get_tool_registry),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Run one chat turn and return the five-field AIChatResponse."""
    outcome = await service.run_chat(
        session=session,
        auth=auth,
        message=body.message,
        conversation_id=body.conversation_id,
        session_id=body.session_id,
        provider=provider,
        registry=registry,
        limiter=limiter,
    )
    meta = {
        "data_source_label": "derived",
        **outcome["meta"],
    }
    return success_envelope(outcome["data"], meta)


@router.get("/ai/tools")
async def ai_tools(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    registry: ToolRegistry = Depends(get_tool_registry),
    limiter: RateLimiter = Depends(get_rate_limiter),
    category: str | None = None,
):
    """List registered tools and declarations (metadata only)."""
    await enforce_rate_limit(session, auth, limiter)
    summaries = [spec.to_summary() for spec in registry.list(category=category)]
    return success_envelope(
        {
            "tools": [ToolSummary(**item).model_dump() for item in summaries],
            "count": len(summaries),
        },
        {
            "data_source_label": "derived",
            "session_id": None,
        },
    )


@router.post("/ai/approval")
async def ai_approval(
    body: ApprovalRequest,
    auth: AuthContext = Depends(require_roles(*MANAGER_PLUS)),
    session: AsyncSession = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Record a human approve/reject decision (no execution path exists)."""
    await enforce_rate_limit(session, auth, limiter)
    approval = await approval_service.decide(
        session,
        auth=auth,
        approval_id=body.approval_id,
        decision=body.decision,
        comment=body.comment,
    )
    view = ApprovalView(
        approval_id=approval.id,
        action=approval.action,
        status=approval.status,
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
        executed=False,
    )
    return success_envelope(
        view.model_dump(),
        {"data_source_label": "derived", "session_id": None},
    )


__all__ = ["router"]

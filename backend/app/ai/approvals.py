"""Approval records and human decisions (Phase 11) — declarative only.

Approving or rejecting **never executes anything**: there is no code path
from an approval record to a business-data mutation. The service only
records the declared action, the human decision, and the audit row.

State machine: ``pending -> approved`` or ``pending -> rejected`` (terminal).
Anything else is a 409 CONFLICT. Scope: organization + approval id.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai import audit
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext
from backend.app.models.ai import AiApproval, ApprovalStatus


async def create_approval(
    session: AsyncSession,
    *,
    auth: AuthContext,
    conversation_id: str,
    action: str,
    declaration: dict[str, Any],
) -> AiApproval:
    """Create one pending approval for a declared action (write-once)."""
    approval = AiApproval(
        conversation_id=conversation_id,
        organization_id=auth.organization_id,
        requested_by=auth.user_id,
        action=action,
        declaration=declaration,
        status=ApprovalStatus.PENDING,
        data_source_label="derived",
    )
    session.add(approval)
    await session.flush()
    return approval


async def get_pending_approval(
    session: AsyncSession,
    approval_id: str,
    organization_id: str,
) -> AiApproval:
    """Load one pending approval scoped to an organization (404 otherwise)."""
    approval = (
        await session.execute(
            select(AiApproval)
            .where(AiApproval.id == approval_id)
            .where(AiApproval.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if approval is None:
        raise APIError(
            ErrorCode.NOT_FOUND,
            f"Approval {approval_id!r} was not found.",
        )
    return approval


async def decide(
    session: AsyncSession,
    *,
    auth: AuthContext,
    approval_id: str,
    decision: str,
    comment: str | None,
    session_id: str | None = None,
) -> AiApproval:
    """Record a human approve/reject decision (no execution follows)."""
    approval = await get_pending_approval(session, approval_id, auth.organization_id)
    if approval.status != ApprovalStatus.PENDING:
        raise APIError(
            ErrorCode.CONFLICT,
            f"Approval {approval_id!r} is already {approval.status}.",
        )
    if decision not in ("approve", "reject"):
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            "Decision must be 'approve' or 'reject'.",
        )
    approval.status = (
        ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
    )
    approval.decided_by = auth.user_id
    approval.decided_at = datetime.now(UTC)
    approval.decision_comment = comment
    await audit.record(
        session,
        action=audit.APPROVAL_DECISION,
        user_id=auth.user_id,
        entity_type="ai_approval",
        entity_id=approval.id,
        session_id=session_id,
        parameters={
            "action": approval.action,
            "decision": decision,
            "status": approval.status,
            "executed": False,
        },
    )
    return approval


__all__ = [
    "create_approval",
    "decide",
    "get_pending_approval",
]

"""Authenticated identity endpoint (Phase 12A) under ``/api/v1/auth/*``.

Returns only non-secret identity metadata for the frontend session bar:
user id, email, role, organization id, and active flag. API keys and
password hashes are never serialized; key provisioning stays a manual
development procedure documented in ``docs/api-contract.md``.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.errors import APIError, ErrorCode, success_envelope
from backend.app.core.security import AuthContext, get_auth_context
from backend.app.models import User

router = APIRouter()


@router.get("/auth/me")
async def read_auth_me(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return the caller's identity metadata (fail closed when unknown)."""
    user = (
        await session.execute(
            select(User).where(
                User.id == auth.user_id,
                User.organization_id == auth.organization_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise APIError(ErrorCode.UNAUTHORIZED)
    return success_envelope(
        {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "is_active": user.is_active,
        },
        {"data_source_label": "derived", "source": "authenticated_identity"},
    )


__all__ = ["router"]

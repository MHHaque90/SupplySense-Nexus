"""Opaque per-user Bearer API-key authentication (Phase 11, decision C1).

Rules fixed by the audit:

- Authorization header only: ``Authorization: Bearer <api key>``.
- Keys are generated as ``ssk_`` + 43 URL-safe characters; only the SHA-256
  hex digest is stored (``users.api_key_hash``). Raw keys are never stored,
  never logged, and never returned after creation.
- Verification is digest equality via :func:`hmac.compare_digest`.
- Fail closed: missing header, malformed header, unknown hash, or an
  inactive user all raise the same 401 ``UNAUTHORIZED`` error.
- Health endpoints remain public (no dependency on this module).
- There is no login flow, no JWT, and no password authentication in the
  API surface (seeded ``password_hash`` values are synthetic markers).
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.errors import APIError, ErrorCode
from backend.app.models import Role, User

API_KEY_PREFIX = "ssk_"
API_KEY_BYTES = 32


@dataclass(frozen=True)
class AuthContext:
    """Authenticated identity exclusively from the API key (never the body)."""

    user_id: str
    organization_id: str
    role: str
    is_active: bool

    @property
    def is_admin(self) -> bool:
        """Administrators hold every role check."""
        return self.role == Role.ADMIN.value


def generate_api_key() -> tuple[str, str]:
    """Return ``(raw_key, sha256_hash)`` for a brand-new API key.

    The raw key is returned exactly once (provisioning time); only the hash
    may be persisted.
    """
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_BYTES)}"
    return raw_key, hash_api_key(raw_key)


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest for a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str | None) -> bool:
    """Constant-time comparison of a raw key against a stored digest."""
    if not stored_hash:
        return False
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash)


def _unauthorized() -> APIError:
    """Single fail-closed 401 for every authentication failure."""
    return APIError(ErrorCode.UNAUTHORIZED)


async def get_auth_context(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> AuthContext:
    """FastAPI dependency resolving ``Authorization: Bearer <key>`` to identity.

    Raises 401 ``UNAUTHORIZED`` on any failure (missing/malformed header,
    unknown key, inactive user). Never reveals which check failed.
    """
    if not authorization:
        raise _unauthorized()
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    digest = hash_api_key(token.strip())
    user = (
        await session.execute(
            select(User).where(User.api_key_hash == digest, User.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if user is None:
        raise _unauthorized()
    return AuthContext(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        is_active=user.is_active,
    )


def require_roles(*roles: str):
    """Dependency factory: allow ``roles`` plus every administrator.

    Returns a FastAPI dependency yielding the :class:`AuthContext` or
    raising 403 ``FORBIDDEN``.
    """
    allowed = set(roles)

    async def _dependency(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if auth.is_admin or auth.role in allowed:
            return auth
        raise APIError(
            ErrorCode.FORBIDDEN,
            f"This endpoint requires role: {', '.join(sorted(allowed))}.",
        )

    return _dependency


__all__ = [
    "API_KEY_PREFIX",
    "AuthContext",
    "generate_api_key",
    "get_auth_context",
    "hash_api_key",
    "require_roles",
    "verify_api_key",
]

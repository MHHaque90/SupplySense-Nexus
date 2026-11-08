"""In-process per-user rate limiting (Phase 11, decision C6).

Fixed tier table from ``docs/ai-assistant-design.md``: sliding hourly and
daily windows per authenticated user; admin is unlimited; the limiter is
**fail-open** (a limiter fault must not take the API down) while
authentication remains **fail-closed**. Denied requests surface as 429
``RATE_LIMIT_EXCEEDED`` with a ``Retry-After`` header (seconds).

The interface (``RateLimiter`` protocol) keeps the door open for another
backend later; the shipped implementation is process-local with no Redis.
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.core.security import AuthContext

logger = logging.getLogger("supplysense.ai.ratelimit")

HOUR_SECONDS = 3600
DAY_SECONDS = 86400

#: role -> (requests_per_hour, requests_per_day); None means unlimited.
RATE_TIERS: dict[str, tuple[int | None, int | None]] = {
    "analyst": (100, 1000),
    "planner": (200, 2000),
    "manager": (500, 5000),
    "executive": (500, 5000),
    "admin": (None, None),
}
DEFAULT_TIER: tuple[int | None, int | None] = (100, 1000)


@dataclass(frozen=True)
class RateDecision:
    """Outcome of one rate-limit check."""

    allowed: bool
    retry_after: int | None = None
    scope: str | None = None

    @classmethod
    def allow(cls) -> "RateDecision":
        """Return an allowed decision."""
        return cls(allowed=True)

    @classmethod
    def deny(cls, retry_after: int, scope: str) -> "RateDecision":
        """Return a denied decision with a bounded retry hint."""
        return cls(allowed=False, retry_after=max(1, int(retry_after)), scope=scope)


class RateLimiter(Protocol):
    """Structural interface for rate-limit backends."""

    async def check(self, user_id: str, role: str) -> RateDecision:
        """Record one request attempt and decide whether it is allowed."""
        ...


class InMemoryRateLimiter:
    """Sliding-window limiter kept in process memory (per user)."""

    def __init__(self, now_fn=None) -> None:
        self._now = now_fn or time.time
        self._hits: dict[str, deque[float]] = {}

    async def check(self, user_id: str, role: str) -> RateDecision:
        """Record an attempt; deny when either window is exhausted."""
        hourly, daily = RATE_TIERS.get(role, DEFAULT_TIER)
        if hourly is None or daily is None:
            return RateDecision.allow()
        now = float(self._now())
        hits = self._hits.setdefault(user_id, deque())
        cutoff_day = now - DAY_SECONDS
        while hits and hits[0] < cutoff_day:
            hits.popleft()
        day_count = len(hits)
        hour_cutoff = now - HOUR_SECONDS
        hour_count = sum(1 for stamp in hits if stamp >= hour_cutoff)
        if day_count >= daily:
            oldest = hits[0]
            return RateDecision.deny(
                math.ceil(oldest + DAY_SECONDS - now), "day"
            )
        if hour_count >= hourly:
            oldest_hour = next(
                stamp for stamp in hits if stamp >= hour_cutoff
            )
            return RateDecision.deny(
                math.ceil(oldest_hour + HOUR_SECONDS - now), "hour"
            )
        hits.append(now)
        return RateDecision.allow()

    def reset(self) -> None:
        """Drop all recorded hits (tests / process recycling)."""
        self._hits.clear()


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Cached limiter resolver (FastAPI dependency; overridable in tests)."""
    global _limiter
    if _limiter is None:
        _limiter = InMemoryRateLimiter()
    return _limiter


def reset_rate_limiter() -> None:
    """Drop the cached limiter so the next request builds a fresh one."""
    global _limiter
    _limiter = None


async def enforce_rate_limit(
    session: "AsyncSession",
    auth: "AuthContext",
    limiter: RateLimiter,
    session_id: str | None = None,
) -> None:
    """Check one request; audit + commit + raise 429 when the tier is spent.

    The explicit commit happens before the raise because the request-level
    session rolls back on exceptions — the audit row must survive.
    """
    try:
        decision = await limiter.check(auth.user_id, auth.role)
    except Exception:  # noqa: BLE001 - fail-open by design (C6)
        logger.exception("rate limiter fault for user %s; failing open", auth.user_id)
        return
    if decision.allowed:
        return
    from backend.app.ai import audit
    from backend.app.core.errors import APIError, ErrorCode

    await audit.record(
        session,
        action=audit.RATE_LIMIT_EXCEEDED,
        user_id=auth.user_id,
        entity_type="ai_rate_limit",
        entity_id=auth.user_id,
        session_id=session_id,
        parameters={"scope": decision.scope, "retry_after": decision.retry_after},
    )
    await session.commit()
    raise APIError(
        ErrorCode.RATE_LIMIT_EXCEEDED,
        ErrorCode.message_for(ErrorCode.RATE_LIMIT_EXCEEDED),
        headers={"Retry-After": str(decision.retry_after)},
    )


__all__ = [
    "DAY_SECONDS",
    "HOUR_SECONDS",
    "InMemoryRateLimiter",
    "RATE_TIERS",
    "RateDecision",
    "RateLimiter",
    "enforce_rate_limit",
    "get_rate_limiter",
    "reset_rate_limiter",
]

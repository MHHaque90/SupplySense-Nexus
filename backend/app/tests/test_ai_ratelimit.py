"""Phase 11 rate-limit tests (C6): tiers, windows, 429, fail-open."""

import pytest
from sqlalchemy import select

from backend.app.ai import ratelimit
from backend.app.ai.ratelimit import (
    RATE_TIERS,
    InMemoryRateLimiter,
    RateDecision,
    enforce_rate_limit,
    get_rate_limiter,
    reset_rate_limiter,
)
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext
from backend.app.main import app
from backend.app.models import AuditEvent
from backend.app.tests.conftest import (
    TestSessionLocal,
    first_organization_id,
    load_tiny_dataset,
    seed_api_user,
)

RAW_ANALYST_KEY = "ssk_test_rl_analyst_" + "a" * 32


class _DenyLimiter:
    async def check(self, user_id: str, role: str) -> RateDecision:
        return RateDecision.deny(42, "hour")


class _FaultyLimiter:
    async def check(self, user_id: str, role: str) -> RateDecision:
        raise RuntimeError("limiter backend down")


@pytest.fixture(autouse=True)
def _clean_limiter():
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def test_tier_table_matches_design():
    assert RATE_TIERS == {
        "analyst": (100, 1000),
        "planner": (200, 2000),
        "manager": (500, 5000),
        "executive": (500, 5000),
        "admin": (None, None),
    }


@pytest.mark.asyncio
async def test_analyst_hourly_cap_denies_request_101():
    clock = {"now": 1_000_000.0}
    limiter = InMemoryRateLimiter(now_fn=lambda: clock["now"])
    for index in range(100):
        decision = await limiter.check("user-1", "analyst")
        assert decision.allowed, index
    denied = await limiter.check("user-1", "analyst")
    assert denied.allowed is False
    assert denied.scope == "hour"
    assert denied.retry_after >= 1


@pytest.mark.asyncio
async def test_hour_window_slides_forward():
    clock = {"now": 1_000_000.0}
    limiter = InMemoryRateLimiter(now_fn=lambda: clock["now"])
    for _ in range(100):
        await limiter.check("user-2", "analyst")
    assert (await limiter.check("user-2", "analyst")).allowed is False
    clock["now"] += ratelimit.HOUR_SECONDS + 1
    assert (await limiter.check("user-2", "analyst")).allowed is True


@pytest.mark.asyncio
async def test_daily_cap_scope(monkeypatch):
    monkeypatch.setitem(RATE_TIERS, "analyst", (100, 3))
    limiter = InMemoryRateLimiter(now_fn=lambda: 1_000_000.0)
    for _ in range(3):
        assert (await limiter.check("user-3", "analyst")).allowed
    denied = await limiter.check("user-3", "analyst")
    assert denied.allowed is False
    assert denied.scope == "day"
    assert denied.retry_after >= 1


@pytest.mark.asyncio
async def test_admin_unlimited():
    limiter = InMemoryRateLimiter()
    for _ in range(250):
        decision = await limiter.check("admin-1", "admin")
        assert decision.allowed


@pytest.mark.asyncio
async def test_enforce_rate_limit_fail_open_on_limiter_fault():
    auth = AuthContext(
        user_id="u", organization_id="o", role="analyst", is_active=True
    )
    async with TestSessionLocal() as session:
        await enforce_rate_limit(session, auth, _FaultyLimiter())
        await session.rollback()


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_429_with_retry_after_and_audit():
    async with TestSessionLocal() as session:
        await load_tiny_dataset(session)
        org_id = await first_organization_id(session)
        user = await seed_api_user(session, org_id, "analyst", RAW_ANALYST_KEY)
        await session.commit()
        auth = AuthContext(
            user_id=user.id,
            organization_id=org_id,
            role="analyst",
            is_active=True,
        )
        with pytest.raises(APIError) as excinfo:
            await enforce_rate_limit(session, auth, _DenyLimiter(), session_id="s-42")
        error = excinfo.value
        assert error.code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert error.status_code == 429
        assert error.headers["Retry-After"] == "42"
        rows = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "ai.ratelimit.exceeded"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].session_id == "s-42"
        await session.rollback()


@pytest.mark.asyncio
async def test_chat_endpoint_429_envelope_and_audit(ai_client):
    async with TestSessionLocal() as session:
        await load_tiny_dataset(session)
        org_id = await first_organization_id(session)
        await seed_api_user(session, org_id, "analyst", RAW_ANALYST_KEY)
        await session.commit()

    app.dependency_overrides[get_rate_limiter] = lambda: _DenyLimiter()
    try:
        response = await ai_client.post(
            "/api/v1/ai/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {RAW_ANALYST_KEY}"},
        )
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert body["error"]["message"] == "Rate limit exceeded. Try again later."

    async with TestSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "ai.ratelimit.exceeded"
                )
            )
        ).scalars().all()
        assert len(rows) == 1

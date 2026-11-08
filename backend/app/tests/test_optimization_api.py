"""Phase 12A optimization endpoint tests (solver status, guards, audit).

Solver statuses are solver vocabulary only; the report must never
translate them into advice (Phase 11 C2) and everything is labeled
``simulated``.
"""

from typing import get_args

from backend.app.ai.ratelimit import RateDecision, get_rate_limiter
from backend.app.ai.ratelimit import reset_rate_limiter as reset_limiter
from backend.app.analytics.optimization import run_optimization
from backend.app.main import app
from backend.app.analytics.optimization.types import OBJECTIVES, STATUSES
from backend.app.api import optimization_router as optimization_router_module
from backend.app.core.config import settings
from backend.app.schemas.analytics import OptimizationObjective, SolverStatus
from backend.app.tests import test_replay_noranking as noranking
from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    RAW_PLANNER_KEY,
    assert_envelope,
    assert_error,
    audit_rows,
    auth,
    reason_text,
    seed_api_org,
)
from backend.app.tests.conftest import TestSessionLocal

_BODY = {
    "objective": "minimize_total_cost",
    "horizon_days": 14,
    "simulation_count": 4,
    "time_limit_seconds": 5,
}


class _DenyLimiter:
    """Limiter double that denies every request with Retry-After=42."""

    async def check(self, user_id: str, role: str) -> RateDecision:
        return RateDecision.deny(42, "api-test-deny")


def test_schema_literals_match_engine_tuples():
    assert list(get_args(OptimizationObjective)) == list(OBJECTIVES)
    assert list(get_args(SolverStatus)) == list(STATUSES)


async def test_optimization_run_reports_solver_status_only(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_OPTIMIZATION", True)
    response = await ai_client.post(
        "/api/v1/optimization/run", headers=auth(RAW_PLANNER_KEY), json=_BODY
    )
    assert response.status_code == 200, response.text
    body = response.json()
    data = assert_envelope(body, label="simulated")
    assert body["meta"]["source"] == "optimization_engine"
    assert data["data_source_label"] == "simulated"
    status = data["feasibility_status"]["status"]
    assert status in STATUSES, status
    limitations = " ".join(body["meta"]["limitations"])
    assert "describes feasibility of the MILP only" in limitations, limitations
    assert "not an instruction to act" in limitations, limitations
    assert "simulated planning outputs" in limitations, limitations
    for key in noranking._walk_keys(data):
        assert key.lower() not in noranking.BANNED_KEYS, f"banned key: {key}"

    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "optimization.run")
    assert len(rows) == 1, rows
    assert rows[0].entity_type == "optimization_run"


async def test_optimization_tradeoff_requires_penalty(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_OPTIMIZATION", True)
    response = await ai_client.post(
        "/api/v1/optimization/run",
        headers=auth(RAW_PLANNER_KEY),
        json={**_BODY, "objective": "cost_shortage_tradeoff"},
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "shortage_penalty" in reason_text(error), error


async def test_optimization_rejects_unknown_objective(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_OPTIMIZATION", True)
    response = await ai_client.post(
        "/api/v1/optimization/run",
        headers=auth(RAW_PLANNER_KEY),
        json={**_BODY, "objective": "minimize_regret"},
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_optimization_rejects_unknown_body_field(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_OPTIMIZATION", True)
    response = await ai_client.post(
        "/api/v1/optimization/run",
        headers=auth(RAW_PLANNER_KEY),
        json={**_BODY, "auto_approve": True},
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_optimization_requires_planning_role(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/optimization/run",
        headers=auth(RAW_ANALYST_KEY),
        json=_BODY,
    )
    assert response.status_code == 403
    assert_error(response.json(), "FORBIDDEN")


async def test_optimization_requires_authentication(ai_client):
    response = await ai_client.post("/api/v1/optimization/run", json=_BODY)
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_optimization_disabled_feature_flag(ai_client, monkeypatch):
    """Disabled optimization must return the structured error before the solver or rate limiter runs."""
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_OPTIMIZATION", False)
    reset_limiter()
    calls: list[None] = []

    def _never_optimize(*args: object, **kwargs: object) -> object:
        calls.append(None)
        raise AssertionError("optimization engine must not run while disabled")

    monkeypatch.setattr(
        optimization_router_module, "run_optimization", _never_optimize
    )
    app.dependency_overrides[get_rate_limiter] = lambda: _DenyLimiter()
    try:
        response = await ai_client.post(
            "/api/v1/optimization/run",
            headers=auth(RAW_PLANNER_KEY),
            json={**_BODY, "simulation_count": 3},
        )
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)
    assert response.status_code == 403, response.text
    error = assert_error(response.json(), "FEATURE_DISABLED")
    assert "disabled" in error["message"].lower(), error
    assert calls == [], "solver must not be entered while disabled"
    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "optimization.run")
    assert len(rows) == 0, "no audit row when a disabled feature never ran"

"""Phase 12A simulation endpoint tests (metadata, compute, guards).

Covers the event-contract metadata, the Monte Carlo run envelope,
determinism for a fixed seed, role/schema/probability guards, the
audit trail, and the shared POST rate limit.
"""

import json
from typing import get_args

from backend.app.ai.ratelimit import RateDecision, get_rate_limiter
from backend.app.ai.ratelimit import reset_rate_limiter as reset_limiter
from backend.app.analytics.simulation import runner as simulation_runner_mod
from backend.app.analytics.simulation.types import EVENT_TYPES
from backend.app.api import simulation_router as simulation_router_module
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.schemas.analytics import EventType
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


class _DenyLimiter:
    """Limiter double that denies every request with Retry-After=42."""

    async def check(self, user_id: str, role: str) -> RateDecision:
        return RateDecision.deny(42, "api-test-deny")


def _strip_volatile(definition: dict) -> dict:
    """Remove per-run identifiers so two runs can be compared."""
    stripped = json.loads(json.dumps(definition))
    stripped.pop("scenario_id", None)
    stripped.pop("name", None)
    event = stripped.get("event")
    if isinstance(event, dict):
        event.pop("event_id", None)
    return stripped


async def test_simulation_events_metadata(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/simulation/events", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="derived")
    assert data["event_types"] == list(EVENT_TYPES)
    assert "SUPPLIER_OUTAGE" in data["templates"], sorted(data["templates"])
    template = data["templates"]["SUPPLIER_OUTAGE"]
    assert template["event_type"] in EVENT_TYPES, template
    assert data["probability_modes"] == ["deterministic", "explicit", "empirical"]
    assert data["bounds"]["horizon_days"] == {"min": 1, "max": 180, "default": 28}
    assert data["bounds"]["simulation_count"] == {"min": 1, "max": 500, "default": 20}
    assert data["bounds"]["random_seed_default"] == 42


def test_schema_event_type_literal_matches_engine():
    assert list(get_args(EventType)) == list(EVENT_TYPES)


async def test_simulation_run_happy_path(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={
            "event_template": "SUPPLIER_OUTAGE",
            "horizon_days": 14,
            "simulation_count": 5,
            "assumptions": ["synthetic API test assumption"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    data = assert_envelope(body, label="simulated")
    assert body["meta"]["source"] == "simulation_engine"
    for key in (
        "disclaimer",
        "synthetic",
        "scenario_definition",
        "simulation_configuration",
        "baseline_outcome",
        "scenario_outcome",
        "delta",
        "stockout_distribution",
        "limitations",
    ):
        assert key in data, key
    assert data["synthetic"] is True
    assert data["data_source_label"] == "simulated"
    assert data["event_type"] in EVENT_TYPES, data["event_type"]
    assert data["probability_mode"] == "deterministic", data["probability_mode"]
    definition = data["scenario_definition"]
    assert definition["scenario_id"].startswith("api-simulation-"), definition
    assert definition["event"]["event_type"] in EVENT_TYPES, definition
    assert isinstance(body["meta"]["limitations"], list)
    assert any(
        "not predictions" in item for item in body["meta"]["limitations"]
    ), body["meta"]["limitations"]

    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "simulation.run")
    assert len(rows) == 1, rows
    assert rows[0].entity_type == "simulation_run"
    assert rows[0].user_id


async def test_simulation_default_template_when_no_event_fields(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={"horizon_days": 7, "simulation_count": 3},
    )
    assert response.status_code == 200, response.text
    data = assert_envelope(response.json(), label="simulated")
    assert data["event_type"] in EVENT_TYPES, data["event_type"]


async def test_simulation_direct_event_type(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={
            "event_type": "DEMAND_SHOCK",
            "demand_multiplier": 1.4,
            "duration_days": 7,
            "simulation_count": 3,
        },
    )
    assert response.status_code == 200, response.text
    data = assert_envelope(response.json(), label="simulated")
    assert data["event_type"] == "DEMAND_SHOCK", data["event_type"]


async def test_simulation_requires_planning_role(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_ANALYST_KEY),
        json={"event_template": "SUPPLIER_OUTAGE"},
    )
    assert response.status_code == 403
    assert_error(response.json(), "FORBIDDEN")


async def test_simulation_rejects_unknown_body_field(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={"event_template": "SUPPLIER_OUTAGE", "unexpected_field": 1},
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_simulation_rejects_template_plus_event_type(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={
            "event_template": "SUPPLIER_OUTAGE",
            "event_type": "DEMAND_SHOCK",
            "simulation_count": 3,
        },
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "at most one" in reason_text(error).lower(), error


async def test_simulation_explicit_probability_requires_value(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    response = await ai_client.post(
        "/api/v1/simulation/run",
        headers=auth(RAW_PLANNER_KEY),
        json={
            "event_template": "SUPPLIER_OUTAGE",
            "probability_mode": "explicit",
            "simulation_count": 3,
        },
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_simulation_is_deterministic_for_same_seed(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    payload = {
        "event_template": "SUPPLIER_OUTAGE",
        "horizon_days": 14,
        "simulation_count": 4,
        "random_seed": 7,
    }
    first = await ai_client.post(
        "/api/v1/simulation/run", headers=auth(RAW_PLANNER_KEY), json=payload
    )
    second = await ai_client.post(
        "/api/v1/simulation/run", headers=auth(RAW_PLANNER_KEY), json=payload
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    report_a = assert_envelope(first.json(), label="simulated")
    report_b = assert_envelope(second.json(), label="simulated")
    for key in (
        "baseline_outcome",
        "scenario_outcome",
        "delta",
        "stockout_distribution",
        "unmet_demand_distribution",
    ):
        assert report_a[key] == report_b[key], key
    assert _strip_volatile(report_a["scenario_definition"]) == _strip_volatile(
        report_b["scenario_definition"]
    )


async def test_simulation_rate_limit_denied_envelope(ai_client, monkeypatch):
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", True)
    reset_limiter()
    app.dependency_overrides[get_rate_limiter] = lambda: _DenyLimiter()
    try:
        response = await ai_client.post(
            "/api/v1/simulation/run",
            headers=auth(RAW_PLANNER_KEY),
            json={"event_template": "SUPPLIER_OUTAGE", "simulation_count": 3},
        )
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "42"
    error = assert_error(response.json(), "RATE_LIMIT_EXCEEDED")
    assert error["message"] == "Rate limit exceeded. Try again later."
    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "ai.ratelimit.exceeded")
    assert len(rows) == 1, rows


async def test_simulation_requires_authentication(ai_client):
    response = await ai_client.post(
        "/api/v1/simulation/run", json={"event_template": "SUPPLIER_OUTAGE"}
    )
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_simulation_disabled_feature_flag(ai_client, monkeypatch):
    """Disabled simulation must return the structured error before the engine or rate limiter runs."""
    await seed_api_org()
    monkeypatch.setattr(settings, "ENABLE_SIMULATION", False)
    reset_limiter()
    calls: list[None] = []

    def _never_run(*args: object, **kwargs: object) -> object:
        calls.append(None)
        raise AssertionError("simulation engine must not run while disabled")

    monkeypatch.setattr(
        simulation_router_module.runner_mod, "run_scenario", _never_run
    )
    app.dependency_overrides[get_rate_limiter] = lambda: _DenyLimiter()
    try:
        response = await ai_client.post(
            "/api/v1/simulation/run",
            headers=auth(RAW_PLANNER_KEY),
            json={"event_template": "SUPPLIER_OUTAGE", "simulation_count": 3},
        )
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)
    assert response.status_code == 403, response.text
    error = assert_error(response.json(), "FEATURE_DISABLED")
    assert "disabled" in error["message"].lower(), error
    assert calls == [], "compute engine must not be entered while disabled"
    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "simulation.run")
    assert len(rows) == 0, "no audit row when a disabled feature never ran"

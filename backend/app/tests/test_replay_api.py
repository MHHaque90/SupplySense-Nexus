"""Phase 12A Decision Replay Lab endpoint tests.

Covers the decision-contract metadata, declared-arm and control-only
runs, the mandatory no-ranking language (Phase 11 C2 discipline), role
and schema guards, and the audit trail.
"""

import json
from typing import get_args

from backend.app.analytics.replay.types import DECISION_TYPES, DEFAULT_REPLAY_CONFIG
from backend.app.schemas.analytics import DecisionType
from backend.app.tests import test_replay_noranking as noranking
from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    RAW_PLANNER_KEY,
    assert_envelope,
    assert_error,
    audit_rows,
    auth,
    seed_api_org,
)
from backend.app.tests.conftest import TestSessionLocal

_BASE_BODY = {
    "event_template": "SUPPLIER_OUTAGE",
    "horizon_days": 14,
    "simulation_count": 4,
}


def _assert_no_ranking_keys(payload: dict) -> None:
    """Reject any ranking/recommendation key in the API report payload."""
    for key in noranking._walk_keys(payload):
        assert key.lower() not in noranking.BANNED_KEYS, f"banned key: {key}"


async def test_replay_decisions_metadata(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/replay/decisions", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="derived")
    assert data["decision_types"] == list(DECISION_TYPES)
    assert data["max_decisions"] == DEFAULT_REPLAY_CONFIG.max_decisions
    assert any("never ranked or recommended" in note for note in data["notes"])


def test_schema_decision_type_literal_matches_engine():
    assert list(get_args(DecisionType)) == list(DECISION_TYPES)


async def test_replay_run_declared_arm_stays_unranked(ai_client):
    await seed_api_org()
    payload = {
        **_BASE_BODY,
        "decisions": [
            {
                "decision_type": "EXPEDITE_INBOUND",
                "description": "synthetic API test arm",
                "quantities": {"expedite_units": 25.0},
                "timing": {"start_day": 0, "end_day": 10, "delay_reduction_days": 3},
            }
        ],
    }
    response = await ai_client.post(
        "/api/v1/replay/run", headers=auth(RAW_PLANNER_KEY), json=payload
    )
    assert response.status_code == 200, response.text
    body = response.json()
    data = assert_envelope(body, label="simulated")
    assert body["meta"]["source"] == "decision_replay_engine"
    comparison = data["decision_to_decision_comparison"]
    assert "no ranking, no scores, no selection" in comparison["semantics"], comparison
    joined_limitations = " ".join(
        list(data.get("limitations") or []) + list(body["meta"]["limitations"])
    )
    assert "never ranks, never recommends, never scores" in joined_limitations
    _assert_no_ranking_keys(data)
    dumped = json.dumps(data, default=str)
    for phrase in (
        '"recommended_option"',
        '"ranked_options"',
        '"ranking":',
        '"confidence":',
        '"score":',
    ):
        assert phrase not in dumped, phrase

    async with TestSessionLocal() as session:
        rows = await audit_rows(session, "replay.run")
    assert len(rows) == 1, rows
    assert rows[0].entity_type == "replay_run"


async def test_replay_empty_decisions_runs_control_only(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/replay/run",
        headers=auth(RAW_PLANNER_KEY),
        json={**_BASE_BODY, "decisions": []},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    data = assert_envelope(body, label="simulated")
    limitations = " ".join(body["meta"]["limitations"])
    assert "Only the NO_ACTION control arm was run" in limitations, limitations
    _assert_no_ranking_keys(data)


async def test_replay_rejects_unknown_decision_type(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/replay/run",
        headers=auth(RAW_PLANNER_KEY),
        json={
            **_BASE_BODY,
            "decisions": [{"decision_type": "BEST_CHOICE"}],
        },
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_replay_rejects_unknown_body_field(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/replay/run",
        headers=auth(RAW_PLANNER_KEY),
        json={**_BASE_BODY, "rank_decisions": True},
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_replay_requires_planning_role(ai_client):
    await seed_api_org()
    response = await ai_client.post(
        "/api/v1/replay/run",
        headers=auth(RAW_ANALYST_KEY),
        json={**_BASE_BODY, "decisions": []},
    )
    assert response.status_code == 403
    assert_error(response.json(), "FORBIDDEN")


async def test_replay_requires_authentication(ai_client):
    response = await ai_client.post(
        "/api/v1/replay/run", json={**_BASE_BODY, "decisions": []}
    )
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

"""Phase 12A dashboard overview tests (KPI families plus risk overview)."""

from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    assert_envelope,
    assert_error,
    auth,
    seed_api_org,
)


async def test_dashboard_overview_envelope_and_label(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/dashboard/overview", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="derived")
    assert body["meta"]["source"] == "phase3_phase7_analytics"
    assert len(data["analysis_date"]) == 10
    assert data["horizon_days"] == 28
    assert set(data["kpis"]) == {"demand", "inventory", "service", "procurement"}
    assert isinstance(data["kpis"]["demand"], list)
    assert isinstance(data["kpis"]["service"], list)
    for metric in data["kpis"]["demand"] + data["kpis"]["service"]:
        assert {"metric_name", "value", "unit"} <= set(metric), metric
    for group in ("inventory", "procurement"):
        families = data["kpis"][group]
        assert isinstance(families, dict) and families, group
        for rows in families.values():
            assert isinstance(rows, list), group
            for metric in rows:
                assert {"metric_name", "value", "unit"} <= set(metric), metric
    overview = data["risk"]
    assert isinstance(overview["records"], int) and overview["records"] >= 1
    assert isinstance(overview["domains"], list) and overview["domains"]
    assert isinstance(overview["severity_counts"], dict)
    persisted = data["forecast_status"]["persisted_forecast_rows"]
    assert isinstance(persisted, int) and persisted >= 0
    assert len(data["limitations"]) >= 3


async def test_dashboard_requires_authentication(ai_client):
    response = await ai_client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")


async def test_dashboard_rejects_invalid_analysis_date(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/dashboard/overview",
        params={"analysis_date": "2024-13-40"},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    assert_error(response.json(), "VALIDATION_ERROR")


async def test_dashboard_horizon_bounds_enforced(ai_client):
    await seed_api_org()
    for bad_horizon in (0, 181):
        response = await ai_client.get(
            "/api/v1/dashboard/overview",
            params={"horizon_days": bad_horizon},
            headers=auth(RAW_ANALYST_KEY),
        )
        assert response.status_code == 422, bad_horizon
        assert_error(response.json(), "VALIDATION_ERROR")

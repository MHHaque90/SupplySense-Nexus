"""Phase 12A risk register endpoint tests (overview, filters, bounds)."""

from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    assert_envelope,
    assert_error,
    assert_page,
    auth,
    reason_text,
    sample_ids,
    seed_api_org,
    seed_two_orgs,
)


async def test_risk_register_shape_and_overview(ai_client):
    await seed_api_org()
    response = await ai_client.get("/api/v1/risk", headers=auth(RAW_ANALYST_KEY))
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase7_risk_register"
    items = assert_page(data)
    assert data["total"] == data["overview"]["records"], data
    assert isinstance(data["overview"]["domains"], list)
    assert isinstance(data["overview"]["severity_counts"], dict)
    for row in items:
        assert {"risk_id", "domain", "severity", "state", "entity_id"} <= set(row), row
    assert data["horizon_days"] == 28
    assert isinstance(data["limitations"], list) and data["limitations"]


async def test_risk_severity_filter_narrows_items_only(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/risk",
        params={"severity": "CRITICAL"},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    for row in items:
        assert row["severity"] == "CRITICAL", row
    assert data["overview"]["records"] >= data["total"], data


async def test_risk_horizon_bounds_enforced(ai_client):
    await seed_api_org()
    for bad_horizon in (0, 181):
        response = await ai_client.get(
            "/api/v1/risk",
            params={"horizon_days": bad_horizon},
            headers=auth(RAW_ANALYST_KEY),
        )
        assert response.status_code == 422, bad_horizon
        assert_error(response.json(), "VALIDATION_ERROR")


async def test_foreign_supplier_filter_is_rejected(ai_client):
    org_ids = await seed_two_orgs()
    _, _, foreign_supplier = await sample_ids(org_ids[1])
    response = await ai_client.get(
        "/api/v1/risk",
        params={"supplier_id": foreign_supplier},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "organization" in reason_text(error).lower(), error


async def test_risk_requires_authentication(ai_client):
    response = await ai_client.get("/api/v1/risk")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

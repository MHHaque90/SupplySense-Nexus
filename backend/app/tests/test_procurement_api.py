"""Phase 12A procurement endpoint tests (KPIs, open orders, inbound, risk)."""

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

INBOUND_STATES = {
    "INBOUND_SUPPORTED",
    "INBOUND_PARTIAL",
    "INBOUND_INSUFFICIENT",
    "NO_KNOWN_INBOUND",
    "UNKNOWN",
}
SIGNALS = {"NO_SIGNAL", "MONITOR", "ELEVATED", "HIGH_EXPOSURE", "UNKNOWN"}


async def test_procurement_overview_kpis(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/procurement/overview", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase3_kpis"
    assert isinstance(data["kpis"], dict) and data["kpis"]
    limitations = " ".join(data["limitations"])
    assert "never a diversification order or ranking" in limitations, limitations


async def test_open_orders_pagination_shape(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/procurement/open-orders", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase6_open_orders"
    items = assert_page(data)
    for row in items:
        assert {
            "po_id",
            "po_number",
            "supplier_id",
            "product_id",
            "arrival_status",
            "overdue",
        } <= set(row), row
    assert len(data["analysis_date"]) == 10


async def test_open_orders_filter_by_supplier(ai_client):
    org_id = await seed_api_org()
    _, _, supplier_id = await sample_ids(org_id)
    response = await ai_client.get(
        "/api/v1/procurement/open-orders",
        params={"supplier_id": supplier_id},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    for row in items:
        assert row["supplier_id"] == supplier_id, row


async def test_inbound_coverage_states(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/procurement/inbound", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase6_inbound_coverage"
    items = assert_page(data)
    assert items, "expected inbound coverage rows for the synthetic dataset"
    for row in items:
        assert {
            "product_id",
            "warehouse_id",
            "state",
            "known_inbound",
            "uncovered_demand",
            "reason",
        } <= set(row), row
        assert row["state"] in INBOUND_STATES, row
    assert data["horizon_days"] == 28


async def test_procurement_risk_signals_are_descriptive(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/procurement/risk", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase6_risk_signals"
    items = assert_page(data)
    assert items, "expected supplier risk signals for the synthetic dataset"
    for row in items:
        assert {
            "supplier_id",
            "product_id",
            "signal",
            "severity",
            "reason",
            "evidence",
            "missing_evidence",
        } <= set(row), row
        assert row["signal"] in SIGNALS, row
    limitations = " ".join(body["meta"]["limitations"])
    assert "never rankings" in limitations, limitations


async def test_foreign_supplier_filter_is_rejected(ai_client):
    org_ids = await seed_two_orgs()
    _, _, foreign_supplier = await sample_ids(org_ids[1])
    response = await ai_client.get(
        "/api/v1/procurement/open-orders",
        params={"supplier_id": foreign_supplier},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "organization" in reason_text(error).lower(), error


async def test_procurement_requires_authentication(ai_client):
    response = await ai_client.get("/api/v1/procurement/overview")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

"""Phase 12A inventory endpoint tests (overview, positions, health)."""

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

HEALTH_STATES = {"STOCKOUT", "CRITICAL", "AT_RISK", "HEALTHY", "EXCESS", "UNKNOWN"}


async def test_inventory_overview_kpi_families(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/inventory/overview", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase3_kpis"
    families = data["kpis"]
    assert "service" in families, sorted(families)
    assert isinstance(families["service"], list)
    grouped = {name: rows for name, rows in families.items() if name != "service"}
    assert grouped, families
    for rows in grouped.values():
        assert isinstance(rows, list), rows
        for metric in rows:
            assert {"metric_name", "value", "unit"} <= set(metric), metric
    for metric in families["service"]:
        assert {"metric_name", "value", "unit"} <= set(metric), metric
    assert len(data["analysis_date"]) == 10
    assert isinstance(data["limitations"], list) and data["limitations"]


async def test_inventory_positions_pagination(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/inventory/positions", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    assert items, "expected inventory positions for the synthetic dataset"
    for row in items:
        assert {"product_id", "warehouse_id"} <= set(row)
    assert len(data["analysis_date"]) == 10


async def test_inventory_positions_filter_by_product(ai_client):
    org_id = await seed_api_org()
    product_id, _, _ = await sample_ids(org_id)
    response = await ai_client.get(
        "/api/v1/inventory/positions",
        params={"product_id": product_id},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    assert items, "expected positions for the filtered product"
    for row in items:
        assert row["product_id"] == product_id, row


async def test_inventory_health_rows_are_rule_based(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/inventory/health", headers=auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    assert items, "expected health rows for the synthetic dataset"
    for row in items:
        assert {
            "product_id",
            "warehouse_id",
            "health",
            "reason",
            "missing_evidence",
        } <= set(row)
        assert row["health"] in HEALTH_STATES, row
        assert isinstance(row["reason"], str)
        assert isinstance(row["missing_evidence"], list)


async def test_inventory_foreign_product_is_rejected(ai_client):
    org_ids = await seed_two_orgs()
    foreign_product, _, _ = await sample_ids(org_ids[1])
    response = await ai_client.get(
        "/api/v1/inventory/positions",
        params={"product_id": foreign_product},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "organization" in reason_text(error).lower(), error


async def test_inventory_requires_authentication(ai_client):
    response = await ai_client.get("/api/v1/inventory/overview")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

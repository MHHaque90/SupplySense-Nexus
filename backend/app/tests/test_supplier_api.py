"""Phase 12A supplier endpoint tests (directory plus performance facts).

Descriptive only: rows stay in supplier-id order and the required
no-ranking disclaimer language is asserted verbatim.
"""

from backend.app.tests.api_support import (
    RAW_ANALYST_KEY,
    assert_envelope,
    assert_error,
    assert_page,
    auth,
    sample_ids,
    seed_api_org,
)


async def test_supplier_directory_is_sorted_and_labeled(ai_client):
    await seed_api_org()
    response = await ai_client.get("/api/v1/suppliers", headers=auth(RAW_ANALYST_KEY))
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "supplier_products"
    items = assert_page(data)
    assert items, "expected supplier rows for the synthetic dataset"
    for row in items:
        assert {"supplier_id", "supplier_name", "country"} <= set(row)
    supplier_ids = [row["supplier_id"] for row in items]
    assert supplier_ids == sorted(supplier_ids), supplier_ids


async def test_supplier_performance_window(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/suppliers/performance",
        params={"page_size": 1},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="synthetic")
    assert body["meta"]["source"] == "phase6_supplier_performance"
    items = assert_page(data, page_size=1)
    assert len(items) <= 1
    assert data["total"] >= 1
    for row in items:
        assert "supplier_id" in row, row
    limitations = " ".join(body["meta"]["limitations"])
    assert "never a ranking" in limitations, limitations


async def test_supplier_performance_single_supplier(ai_client):
    org_id = await seed_api_org()
    _, _, supplier_id = await sample_ids(org_id)
    response = await ai_client.get(
        "/api/v1/suppliers/performance",
        params={"supplier_id": supplier_id},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="synthetic")
    items = assert_page(data)
    assert len(items) == 1, items
    assert items[0]["supplier_id"] == supplier_id


async def test_supplier_directory_disclaims_ranking(ai_client):
    await seed_api_org()
    response = await ai_client.get("/api/v1/suppliers", headers=auth(RAW_ANALYST_KEY))
    limitations = " ".join(response.json()["meta"]["limitations"])
    assert "deduplicated supplier" in limitations, limitations


async def test_suppliers_require_authentication(ai_client):
    response = await ai_client.get("/api/v1/suppliers")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

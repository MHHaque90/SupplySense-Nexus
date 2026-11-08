"""Phase 12A forecast endpoint tests (label, slicing, org isolation)."""

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


async def test_forecast_rows_are_labeled_estimates(ai_client):
    await seed_api_org()
    response = await ai_client.get("/api/v1/forecast", headers=auth(RAW_ANALYST_KEY))
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="forecast")
    assert body["meta"]["source"] == "phase4_forecasting"
    items = assert_page(data)
    assert items, "expected forecast series for the synthetic dataset"
    row = items[0]
    for key in (
        "series_id",
        "product_id",
        "warehouse_id",
        "forecast_dates",
        "point",
        "lower",
        "upper",
        "horizon",
        "missing",
    ):
        assert key in row, key
    assert (
        len(row["point"])
        == len(row["lower"])
        == len(row["upper"])
        == len(row["forecast_dates"])
        == row["horizon"]
    )
    assert 1 <= row["horizon"] <= 366
    assert isinstance(body["meta"]["limitations"], list)


async def test_forecast_horizon_and_pagination(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/forecast",
        params={"horizon": 5, "page": 2, "page_size": 2},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200
    data = assert_envelope(response.json(), label="forecast")
    items = assert_page(data, page=2, page_size=2)
    assert len(items) <= 2
    for row in items:
        assert row["horizon"] <= 5


async def test_forecast_rejects_reversed_date_window(ai_client):
    await seed_api_org()
    response = await ai_client.get(
        "/api/v1/forecast",
        params={"start_date": "2025-02-01", "end_date": "2025-01-01"},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "start_date" in reason_text(error), error


async def test_forecast_foreign_series_is_rejected(ai_client):
    org_ids = await seed_two_orgs()
    foreign_product, _, _ = await sample_ids(org_ids[1])
    response = await ai_client.get(
        "/api/v1/forecast",
        params={"product_id": foreign_product},
        headers=auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    error = assert_error(response.json(), "VALIDATION_ERROR")
    assert "organization" in reason_text(error).lower(), error


async def test_forecast_requires_authentication(ai_client):
    response = await ai_client.get("/api/v1/forecast")
    assert response.status_code == 401
    assert_error(response.json(), "UNAUTHORIZED")

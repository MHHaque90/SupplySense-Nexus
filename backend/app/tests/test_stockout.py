"""Phase 5 stockout exposure tests."""

from backend.app.analytics.inventory import projection, stockout
from backend.app.analytics.inventory.types import (
    DEFAULT_INVENTORY_CONFIG,
    ForecastInput,
)


def _forecast(point):
    total = len(point)
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
        horizon=total, point=list(point),
        lower=list(point), upper=list(point),
    )


def _exposure(on_hand, demand):
    forecast = _forecast(demand)
    trajectory = projection.project_trajectory(on_hand, forecast)
    return stockout.assess_exposure(
        "P1", "W1", on_hand, forecast, trajectory, DEFAULT_INVENTORY_CONFIG
    )


def test_current_stockout_is_immediate():
    result = _exposure(0.0, [10.0] * 10)
    assert result.current_stockout is True
    assert result.exposure == "immediate"
    assert result.days_until_stockout == 0


def test_projected_stockout_within_horizon():
    result = _exposure(25.0, [10.0] * 10)
    assert result.projected_stockout is True
    assert result.projected_stockout_date == "2026-07-03"
    assert result.days_until_stockout == 2
    assert result.horizon_stockout is True
    assert result.exposure == "elevated"
    assert result.demand_remaining_at_stockout == 80.0


def test_watch_beyond_urgency_window():
    result = _exposure(95.0, [10.0] * 10)
    assert result.exposure == "watch"
    assert result.days_until_stockout == 9


def test_no_stockout_when_covered():
    result = _exposure(500.0, [10.0] * 10)
    assert result.exposure == "no_exposure"
    assert result.projected_stockout is False
    assert result.projected_stockout_date is None


def test_missing_forecast_is_unknown():
    result = stockout.assess_exposure("P1", "W1", 50.0, None, [], DEFAULT_INVENTORY_CONFIG)
    assert result.exposure == "unknown"
    result = stockout.assess_exposure("P1", "W1", None, _forecast([5.0]), [], DEFAULT_INVENTORY_CONFIG)
    assert result.exposure == "unknown"

"""Phase 5 coverage and days-of-supply tests."""

from backend.app.analytics.inventory import coverage
from backend.app.analytics.inventory.types import ForecastInput


def _forecast(point, lower=None, upper=None):
    total = len(point)
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
        horizon=total, point=list(point),
        lower=list(lower or point), upper=list(upper or point),
    )


def test_normal_demand_coverage():
    result = coverage.forecast_coverage("P1", "W1", 100.0, _forecast([10.0] * 10))
    assert result.forecast_days_of_supply == 10.0
    assert result.forecast_days_of_supply_state == "finite"
    assert result.coverage_ratio_point == 1.0
    assert result.horizon_demand_point == 100.0


def test_zero_demand_is_unbounded():
    result = coverage.forecast_coverage("P1", "W1", 50.0, _forecast([0.0] * 10))
    assert result.forecast_days_of_supply_state == "unbounded"
    assert result.forecast_days_of_supply is None
    assert result.coverage_ratio_point is None


def test_zero_inventory_zero_demand_is_unknown():
    result = coverage.forecast_coverage("P1", "W1", 0.0, _forecast([0.0] * 5))
    assert result.forecast_days_of_supply_state == "unknown"


def test_high_and_low_demand_bounds():
    forecast = _forecast([10.0, 10.0], lower=[5.0, 5.0], upper=[20.0, 20.0])
    result = coverage.forecast_coverage("P1", "W1", 60.0, forecast)
    assert result.coverage_ratio_point == 3.0
    assert result.coverage_ratio_lower_demand == 6.0
    assert result.coverage_ratio_upper_demand == 1.5
    assert result.horizon_demand_lower == 10.0
    assert result.horizon_demand_upper == 40.0


def test_missing_forecast_and_inventory():
    result = coverage.forecast_coverage("P1", "W1", 100.0, None)
    assert result.forecast_days_of_supply is None
    assert result.forecast_days_of_supply_state == "unknown"
    assert result.historical_days_of_supply is None
    result = coverage.forecast_coverage("P1", "W1", None, _forecast([5.0] * 4))
    assert result.forecast_days_of_supply is None


def test_historical_dos_labeled_separately():
    result = coverage.forecast_coverage(
        "P1", "W1", 100.0, _forecast([10.0] * 10), historical_daily_demand=20.0
    )
    assert result.forecast_days_of_supply == 10.0
    assert result.historical_days_of_supply == 5.0


def test_invalid_values_rejected_by_domain():
    # Negative on-hand cannot occur from the loader; contract keeps the value
    # visible rather than silently correcting it.
    result = coverage.forecast_coverage("P1", "W1", -5.0, _forecast([10.0] * 5))
    assert result.forecast_days_of_supply == -0.5
    assert result.forecast_days_of_supply_state == "finite"

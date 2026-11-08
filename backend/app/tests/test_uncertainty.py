"""Phase 5 uncertainty propagation tests (consume intervals, never recompute)."""

from backend.app.analytics.inventory import uncertainty
from backend.app.analytics.inventory.types import ForecastInput


def _forecast():
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=["2026-07-01", "2026-07-02"],
        horizon=2, point=[10.0, 20.0], lower=[8.0, 15.0], upper=[14.0, 28.0],
        confidence_level=0.95,
    )


def test_uncertainty_note_names_all_three_cases():
    note = uncertainty.uncertainty_note(_forecast())
    lowered = note.lower()
    assert "upper forecast-bound scenario" in lowered
    assert "point 30" in note
    assert "lower-bound 23" in note
    assert "worst" not in lowered
    assert "guarantee" not in lowered


def test_missing_forecast_note():
    assert "unknown" in uncertainty.uncertainty_note(None).lower()
    missing = ForecastInput(product_id="P1", warehouse_id="W1", origin="2026-06-30", missing=True)
    assert "unknown" in uncertainty.uncertainty_note(missing).lower()


def test_coverage_ordering_point_between_bounds():
    forecast = _forecast()
    assert sum(forecast.lower) <= sum(forecast.point) <= sum(forecast.upper)

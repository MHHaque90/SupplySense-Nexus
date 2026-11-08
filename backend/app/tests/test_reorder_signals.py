"""Phase 5 reorder signal tests (signals only, never quantities)."""

from backend.app.analytics.inventory import reorder_signals
from backend.app.analytics.inventory.types import (
    DEFAULT_INVENTORY_CONFIG,
    ForecastInput,
    StockoutExposure,
)

CONFIG = DEFAULT_INVENTORY_CONFIG


def _forecast(point):
    total = len(point)
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
        horizon=total, point=list(point),
        lower=list(point), upper=[value * 1.5 for value in point],
    )


def _stockout(days=None):
    return StockoutExposure(
        product_id="P1", warehouse_id="W1",
        projected_stockout=days is not None, days_until_stockout=days,
        exposure="watch" if days is not None else "no_exposure",
    )


def test_no_signal_above_threshold():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 500.0, _forecast([10.0] * 14), _stockout(), 50.0, CONFIG
    )
    assert signal.urgency == "no_signal"
    assert signal.below_threshold is False
    assert signal.threshold is not None and signal.threshold > 0


def test_monitor_below_threshold_far_stockout():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 100.0, _forecast([10.0] * 14), _stockout(20), 10.0, CONFIG
    )
    assert signal.below_threshold is True
    assert signal.urgency == "monitor"


def test_plan_within_plan_window():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 100.0, _forecast([10.0] * 14), _stockout(10), 10.0, CONFIG
    )
    assert signal.urgency == "plan"


def test_urgent_imminent_stockout():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 100.0, _forecast([10.0] * 14), _stockout(2), 10.0, CONFIG
    )
    assert signal.urgency == "urgent"
    assert "no order quantity" in signal.reason.lower() or "signal only" in signal.reason


def test_urgent_critical_dos_without_trajectory():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 20.0, _forecast([10.0] * 14), _stockout(), 2.0, CONFIG
    )
    assert signal.urgency == "urgent"


def test_unknown_without_inputs():
    signal = reorder_signals.reorder_signal(
        "P1", "W1", None, _forecast([10.0] * 14), _stockout(), 5.0, CONFIG
    )
    assert signal.urgency == "unknown"
    signal = reorder_signals.reorder_signal(
        "P1", "W1", 50.0, None, _stockout(), 5.0, CONFIG
    )
    assert signal.urgency == "unknown"


def test_threshold_uses_documented_buffer():
    threshold, buffer = reorder_signals.reorder_threshold(_forecast([10.0] * 14), CONFIG)
    assert threshold is not None and buffer is not None
    assert buffer >= 0
    assert threshold >= 10.0 * CONFIG.coverage_period_days
    empty_threshold, _ = reorder_signals.reorder_threshold(None, CONFIG)
    assert empty_threshold is None

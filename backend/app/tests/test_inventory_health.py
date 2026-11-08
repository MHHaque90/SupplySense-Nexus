"""Phase 5 inventory health classification tests (all six states + boundaries)."""

from backend.app.analytics.inventory import health
from backend.app.analytics.inventory.types import (
    DEFAULT_INVENTORY_CONFIG,
    CoverageResult,
    ForecastInput,
    InventoryPosition,
    StockoutExposure,
)

CONFIG = DEFAULT_INVENTORY_CONFIG


def _position(on_hand):
    return InventoryPosition(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        current_on_hand=on_hand, latest_snapshot_date="2026-06-30",
    )


def _forecast():
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=["2026-07-01"], horizon=1,
        point=[10.0], lower=[8.0], upper=[12.0],
    )


def _coverage(dos=None, state="unknown", ratio=None):
    return CoverageResult(
        product_id="P1", warehouse_id="W1",
        forecast_days_of_supply=dos, forecast_days_of_supply_state=state,
        coverage_ratio_point=ratio,
    )


def _stockout(exposure, days=None):
    return StockoutExposure(
        product_id="P1", warehouse_id="W1", projected_stockout=exposure != "no_exposure",
        days_until_stockout=days, projected_stockout_date="2026-07-05" if days is not None else None,
        exposure=exposure,
    )


def test_stockout_state():
    result = health.classify_health(_position(0.0), _forecast(), None, None, CONFIG)
    assert result.health == "STOCKOUT"
    assert "stocked out" in result.reason


def test_critical_projected_stockout():
    result = health.classify_health(
        _position(20.0), _forecast(), _coverage(2.0, "finite"),
        _stockout("elevated", 2), CONFIG,
    )
    assert result.health == "CRITICAL"
    assert "2 days" in result.reason


def test_critical_low_dos_boundary():
    result = health.classify_health(
        _position(30.0), _forecast(), _coverage(3.0, "finite"),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "CRITICAL"


def test_at_risk_watch_and_dos_boundary():
    result = health.classify_health(
        _position(50.0), _forecast(), _coverage(20.0, "finite"),
        _stockout("watch", 9), CONFIG,
    )
    assert result.health == "AT_RISK"
    assert "9 days" in result.reason
    result = health.classify_health(
        _position(70.0), _forecast(), _coverage(7.0, "finite"),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "AT_RISK"


def test_healthy_adequate_coverage():
    result = health.classify_health(
        _position(200.0), _forecast(), _coverage(20.0, "finite", ratio=1.5),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "HEALTHY"


def test_healthy_unbounded_zero_demand():
    result = health.classify_health(
        _position(40.0), _forecast(), _coverage(None, "unbounded"),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "HEALTHY"


def test_excess_high_dos_and_ratio():
    result = health.classify_health(
        _position(700.0), _forecast(), _coverage(70.0, "finite", ratio=1.0),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "EXCESS"
    assert "Descriptive only" in result.reason
    result = health.classify_health(
        _position(300.0), _forecast(), _coverage(30.0, "finite", ratio=2.5),
        _stockout("no_exposure"), CONFIG,
    )
    assert result.health == "EXCESS"


def test_unknown_without_position_or_coverage():
    unknown_pos = _position(None)
    unknown_pos.unknown = True
    result = health.classify_health(unknown_pos, None, None, None, CONFIG)
    assert result.health == "UNKNOWN"
    assert "inventory_position" in result.missing_evidence
    result = health.classify_health(
        _position(100.0), None, _coverage(), _stockout("unknown"), CONFIG
    )
    assert result.health == "UNKNOWN"
    assert "forecast" in result.missing_evidence


def test_service_warning_surfaces_attention():
    result = health.classify_health(
        _position(200.0), _forecast(), _coverage(20.0, "finite", ratio=1.5),
        _stockout("no_exposure"), CONFIG, service_warning=True,
    )
    assert result.health == "AT_RISK"
    assert "attention" in result.reason

"""Phase 5 forecast-to-inventory integration tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory import forecast_inputs
from backend.app.analytics.inventory.types import ForecastInput


def _persisted_frame():
    return pd.DataFrame({
        "product_id": ["P1"] * 3,
        "warehouse_id": ["W1"] * 3,
        "forecast_date": [date(2026, 7, d) for d in (1, 2, 3)],
        "point": [10.0, 12.0, 9.0],
        "lower": [8.0, 9.0, 7.0],
        "upper": [12.0, 15.0, 11.0],
        "confidence_level": [0.95] * 3,
        "horizon": [3] * 3,
        "model_version_id": ["V1"] * 3,
        "model_name": ["seasonal_naive"] * 3,
        "model_version": ["4.0.0"] * 3,
        "model_type": ["baseline"] * 3,
        "model_metrics": [None] * 3,
    })


def _input(**overrides):
    base = {
        "product_id": "P1", "warehouse_id": "W1", "origin": "2026-06-30",
        "forecast_dates": ["2026-07-01", "2026-07-02"],
        "horizon": 2, "point": [10.0, 12.0], "lower": [8.0, 9.0],
        "upper": [12.0, 15.0], "model_name": "seasonal_naive",
        "model_version": "4.0.0",
    }
    base.update(overrides)
    return ForecastInput(**base)


def test_persisted_rows_group_into_series_inputs():
    inputs = forecast_inputs.frame_to_inputs(_persisted_frame())
    assert set(inputs) == {"P1|W1"}
    result = inputs["P1|W1"]
    assert result.point == [10.0, 12.0, 9.0]
    assert result.source == "persisted"
    assert not result.missing
    assert result.origin == "2026-06-30"
    assert result.model_name == "seasonal_naive"


def test_empty_persisted_frame_yields_no_inputs():
    assert forecast_inputs.frame_to_inputs(pd.DataFrame()) == {}


def test_missing_forecast_state_is_explicit():
    result = forecast_inputs.missing_forecast("P9", "W9", "2026-06-30")
    assert result.missing is True
    assert result.point == [] and result.horizon == 0


def test_generated_inputs_carry_provenance():
    demand = pd.DataFrame({
        "product_id": ["P1"] * 120,
        "warehouse_id": ["W1"] * 120,
        "date": pd.date_range("2025-01-01", periods=120, freq="D").date,
        "quantity": [10.0 + (i % 7) for i in range(120)],
    })
    from backend.app.analytics.config import AnalyticsConfig

    config = AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60)
    inputs = forecast_inputs.generate_inputs(demand, date(2025, 4, 30), config)
    assert set(inputs) == {"P1|W1"}
    result = inputs["P1|W1"]
    assert result.source == "generated_for_analysis"
    assert result.model_name and result.validation_metric
    assert len(result.point) == 7


def test_input_contract_serializes():
    payload = _input().to_dict()
    assert payload["source"] == "persisted"
    assert payload["missing"] is False
    assert payload["model_name"] == "seasonal_naive"
    assert payload["model_version"] == "4.0.0"
    assert len(payload["point"]) == len(payload["lower"]) == len(payload["upper"]) == 2

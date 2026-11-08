"""Phase 8 baseline-vs-scenario comparison tests."""

from backend.app.analytics.simulation.comparison import compare
from backend.app.analytics.simulation.types import ScenarioOutcome


def _outcome(label, **overrides):
    params = {
        "stockout_probability": 0.0, "expected_unmet_demand": 0.0,
        "expected_min_inventory": 100.0, "expected_ending_inventory": 100.0,
        "expected_stockout_days": 0.0, "service_exposure_probability": 0.0,
    }
    params.update(overrides)
    outcome = ScenarioOutcome(label=label)
    for key, value in params.items():
        setattr(outcome, key, value)
    return outcome


def test_delta_calculations():
    baseline = _outcome("baseline")
    scenario = _outcome(
        "scenario", stockout_probability=0.5, expected_unmet_demand=30.0,
        expected_min_inventory=0.0, expected_ending_inventory=10.0,
        expected_stockout_days=3.0, service_exposure_probability=0.5,
    )
    deltas = compare(baseline, scenario)
    assert deltas["delta_stockout_probability"] == 0.5
    assert deltas["delta_unmet_demand"] == 30.0
    assert deltas["delta_min_inventory"] == -100.0
    assert deltas["delta_ending_inventory"] == -90.0
    assert deltas["delta_stockout_days"] == 3.0
    assert deltas["delta_service_exposure"] == 0.5


def test_missing_metrics_yield_none_deltas():
    baseline = _outcome("baseline")
    scenario = _outcome("scenario")
    scenario.stockout_probability = None
    deltas = compare(baseline, scenario)
    assert deltas["delta_stockout_probability"] is None
    assert deltas["delta_unmet_demand"] == 0.0


def test_identical_outcomes_zero_delta():
    deltas = compare(_outcome("baseline"), _outcome("scenario"))
    assert all(value == 0.0 for value in deltas.values())

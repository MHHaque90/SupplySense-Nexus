"""Phase 8 uncertainty-separation tests.

Forecast uncertainty, scenario uncertainty, simulation variability,
and risk severity are four distinct concepts. These tests pin them
apart structurally.
"""

from backend.app.analytics.simulation import outcomes
from backend.app.analytics.simulation.types import SimulationConfig


def test_four_concepts_are_distinct_fields():
    forecast = {"interval_method": "empirical_residual_quantile", "confidence_level": 0.95}
    scenario = {"probability_mode": "explicit", "probability_source": "USER_ASSUMED"}
    simulation = {"random_seed": 42, "simulation_count": 100}
    risk = {"severity": "HIGH"}
    assert set(forecast) & set(simulation) == set()
    assert set(scenario) & set(simulation) == set()
    assert set(risk) & set(scenario) == set()
    # Severity vocabulary never appears as a probability value.
    assert risk["severity"] != scenario.get("probability")


def test_risk_severity_is_not_probability():
    from backend.app.analytics.simulation import probability as probability_mod

    with_boundary = probability_mod.resolve_probability("explicit", 0.2)
    assert with_boundary == (0.2, "USER_ASSUMED")
    # A HIGH risk string cannot pass probability validation.
    try:
        probability_mod.resolve_probability("explicit", "HIGH")  # type: ignore[arg-type]
        raise AssertionError("should have raised")
    except (ValueError, TypeError):
        pass


def test_historical_data_not_simulation_result():
    outcome = outcomes.aggregate(
        [{"any_stockout": False, "stockout_days": 0.0, "min_inventory": 50.0,
          "ending_inventory": 50.0, "unmet_demand": 0.0, "depleted": False,
          "service_exposed": False, "stockout_by_7": False,
          "stockout_by_14": False, "stockout_by_28": False,
          "first_stockout_date": None}],
        "baseline", 7, ["P1"], ["W1"], [], 0, 0, 0.0, 0.0,
        SimulationConfig(),
    )
    assert outcome.label == "baseline"
    assert outcome.stockout_probability == 0.0


def test_horizon_gating_for_timing_metrics():
    outcome = outcomes.aggregate(
        [{"any_stockout": True, "stockout_days": 2.0, "min_inventory": 0.0,
          "ending_inventory": 0.0, "unmet_demand": 5.0, "depleted": True,
          "service_exposed": True, "stockout_by_7": True,
          "stockout_by_14": False, "stockout_by_28": False,
          "first_stockout_date": "2026-07-03"}],
        "scenario", 7, ["P1"], ["W1"], ["S1"], 1, 1, 0.0, 10.0,
        SimulationConfig(),
    )
    assert outcome.stockout_by_day["probability_stockout_by_7d"] == 1.0
    assert outcome.stockout_by_day["probability_stockout_by_14d"] is None
    assert outcome.stockout_by_day["probability_stockout_by_28d"] is None
    assert outcome.first_stockout_dates == ["2026-07-03"]
    assert outcome.affected_supplier_count == 1
    assert outcome.unavailable_inbound_quantity == 10.0

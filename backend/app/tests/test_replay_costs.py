"""Phase 9 cost assembly tests (observed vs assumed, never fabricated)."""

import pandas as pd
import pytest

from backend.app.analytics.replay import costs, decisions


def _links():
    return pd.DataFrame({
        "supplier_id": ["S1"],
        "product_id": ["P1"],
        "unit_cost": ["12.50"],
    })


def _decision(**overrides):
    params = {
        "affected_suppliers": ["S1"], "affected_products": ["P1"],
        "quantities": {"order_units": 40.0},
    }
    params.update(overrides)
    return decisions.build_decision("R1", "PURCHASE_ORDER_ADJUSTMENT", **params)


def test_observed_purchase_cost():
    result = costs.compute_costs(_decision(), {"order_units": 40.0}, _links())
    assert result["decision_cost"] == 500.0
    assert result["cost_notes"]["order_units@observed"] == "OBSERVED_PURCHASE_COST"
    assert result["disruption_cost"] is None
    assert result["total_modeled_cost"] == 500.0


def test_explicit_assumed_cost():
    decision = _decision(cost_assumptions={"expedite_cost": 5000.0})
    result = costs.compute_costs(decision, {"order_units": 40.0}, _links())
    assert result["decision_cost"] == 5500.0
    assert result["cost_notes"]["expedite_cost"] == "USER_ASSUMED_COST"


def test_missing_cost_is_none_not_zero():
    decision = decisions.build_decision("R1", "NO_ACTION")
    result = costs.compute_costs(decision, {}, pd.DataFrame())
    assert result["decision_cost"] is None
    assert result["disruption_cost"] is None
    assert result["total_modeled_cost"] is None
    assert "No cost assumptions" in result["cost_notes"]["total"]


def test_disruption_cost_requires_explicit_rate():
    result = costs.compute_costs(
        _decision(), {"order_units": 40.0}, _links(),
        disruption_cost_per_unmet_unit=2.0, unmet_demand=30.0,
    )
    assert result["disruption_cost"] == 60.0
    assert result["total_modeled_cost"] == 560.0


def test_negative_cost_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        costs.compute_costs(
            _decision(cost_assumptions={"expedite_cost": -10.0}),
            {"order_units": 1.0}, _links(),
        )
    with pytest.raises(ValueError, match="non-negative"):
        costs.compute_costs(
            _decision(), {"order_units": 1.0}, _links(),
            disruption_cost_per_unmet_unit=-1.0, unmet_demand=5.0,
        )


def test_no_best_or_optimal_cost_keys():
    result = costs.compute_costs(_decision(), {"order_units": 40.0}, _links())
    for banned in ("best_cost", "optimal_cost", "minimum_cost"):
        assert banned not in result

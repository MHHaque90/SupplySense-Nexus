"""Outcome aggregation for simulation runs (Phase 8).

Aggregates per-iteration engine outputs into inventory, service,
supply, and timing outcomes. Timing probabilities (7/14/28d) are only
exposed when the horizon covers them. Percentile names are used
consistently (p90/p95 for unmet demand).
"""

import numpy as np

from backend.app.analytics.simulation import monte_carlo
from backend.app.analytics.simulation.types import ScenarioOutcome, SimulationConfig


def _percentile(values: list[float], level: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), level))


def aggregate(
    iterations: list[dict[str, object]],
    label: str,
    horizon_days: int,
    affected_products: list[str],
    affected_warehouses: list[str],
    affected_suppliers: list[str],
    affected_pairs: int,
    affected_inbound: int,
    delayed_qty: float,
    unavailable_qty: float,
    config: SimulationConfig,
) -> ScenarioOutcome:
    """Aggregate iteration outputs into a typed outcome."""
    total = len(iterations)
    if total == 0:
        raise ValueError("No iterations to aggregate.")
    any_stockout = [bool(it["any_stockout"]) for it in iterations]
    stockout_days = [float(it["stockout_days"]) for it in iterations]
    min_inv = [float(it["min_inventory"]) for it in iterations]
    end_inv = [float(it["ending_inventory"]) for it in iterations]
    unmet = [float(it["unmet_demand"]) for it in iterations]
    depleted = [bool(it["depleted"]) for it in iterations]
    exposed = [bool(it["service_exposed"]) for it in iterations]
    outcome = ScenarioOutcome(label=label)
    outcome.stockout_count = sum(1 for flag in any_stockout if flag)
    if total >= 1:
        outcome.stockout_probability = monte_carlo.stockout_probability(any_stockout)
        outcome.expected_stockout_days = float(np.mean(stockout_days))
        outcome.expected_min_inventory = float(np.mean(min_inv))
        outcome.expected_ending_inventory = float(np.mean(end_inv))
        outcome.inventory_depletion_probability = float(
            sum(1 for flag in depleted if flag) / total)
        outcome.service_exposure_probability = float(
            sum(1 for flag in exposed if flag) / total)
        outcome.expected_unmet_demand = float(np.mean(unmet))
        outcome.median_unmet_demand = float(np.median(unmet))
    if total >= config.min_simulations_percentiles:
        outcome.p90_unmet_demand = _percentile(unmet, 90)
        outcome.p95_unmet_demand = _percentile(unmet, 95)
        outcome.distributions["unmet_demand"] = monte_carlo.distribution_stats(
            unmet, total, config)
        outcome.distributions["ending_inventory"] = monte_carlo.distribution_stats(
            end_inv, total, config)
    outcome.affected_product_count = len(set(affected_products))
    outcome.affected_warehouse_count = len(set(affected_warehouses))
    outcome.affected_supplier_count = len(set(affected_suppliers))
    outcome.affected_supplier_product_count = affected_pairs
    outcome.affected_inbound_count = affected_inbound
    outcome.delayed_inbound_quantity = delayed_qty
    outcome.unavailable_inbound_quantity = unavailable_qty
    for day in (7, 14, 28):
        if horizon_days >= day:
            outcome.stockout_by_day[f"probability_stockout_by_{day}d"] = float(
                sum(1 for it in iterations if it.get(f"stockout_by_{day}", False)) / total)
        else:
            outcome.stockout_by_day[f"probability_stockout_by_{day}d"] = None
    outcome.first_stockout_dates = [
        str(it["first_stockout_date"]) if it["first_stockout_date"] is not None else None
        for it in iterations
    ]
    return outcome

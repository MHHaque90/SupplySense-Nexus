"""Traceability assembly for simulated outcomes (Phase 8).

Every outcome links: scenario → event → affected entity →
supplier/product/warehouse → baseline inventory → forecast →
inbound → simulation result, so a user can answer why a product
was affected.
"""

from typing import Any

from backend.app.analytics.simulation.types import SimulationScenario


def build_trace(
    scenario: SimulationScenario,
    product_id: str,
    warehouse_id: str,
    supplier_ids: list[str],
    forecast_meta: dict[str, Any],
    baseline_on_hand: float,
    inbound_sources: list[str],
) -> dict[str, Any]:
    """Assemble the provenance chain for one affected entity."""
    event = scenario.event
    return {
        "scenario_id": scenario.scenario_id,
        "event_id": event.event_id if event else None,
        "event_type": event.event_type if event else None,
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "supplier_ids": sorted(set(supplier_ids)),
        "baseline_on_hand": baseline_on_hand,
        "forecast_model": forecast_meta.get("model_name"),
        "forecast_origin": forecast_meta.get("origin"),
        "forecast_horizon": forecast_meta.get("horizon"),
        "inbound_sources": sorted(set(inbound_sources)),
        "probability_mode": scenario.probability_mode,
        "probability_source": scenario.probability_source,
        "random_seed": scenario.random_seed,
        "simulation_count": scenario.simulation_count,
        "selection_basis": scenario.selection_basis,
        "data_source_label": "simulated",
    }

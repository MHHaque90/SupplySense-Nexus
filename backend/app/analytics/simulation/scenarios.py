"""Scenario construction and validation (Phase 8)."""

from backend.app.analytics.simulation import events
from backend.app.analytics.simulation.probability import resolve_probability
from backend.app.analytics.simulation.types import (
    DEFAULT_SIMULATION_CONFIG,
    SimulationConfig,
    SimulationScenario,
)


def build_scenario(
    scenario_id: str,
    event,
    analysis_date: str,
    horizon_days: int = 28,
    affected_entities: list | None = None,
    probability_mode: str = "deterministic",
    probability: float | None = None,
    simulation_count: int = 1,
    random_seed: int = 42,
    selection_basis: str = "explicit_user_selection",
    name: str = "",
    description: str = "",
    config: SimulationConfig | None = None,
) -> SimulationScenario:
    """Validate parameters and assemble a scenario contract."""
    config = config or DEFAULT_SIMULATION_CONFIG
    if not 1 <= horizon_days <= config.max_horizon_days:
        raise ValueError(
            f"horizon_days must be within [1, {config.max_horizon_days}]."
        )
    if simulation_count < 1:
        raise ValueError("simulation_count must be at least 1.")
    # Default event targeting from explicitly resolved entities, then
    # validate the complete event (documented defaulting rule).
    entities = list(affected_entities or [])
    if not event.affected_suppliers:
        event.affected_suppliers = sorted({
            str(item["supplier_id"]) for item in entities if item.get("supplier_id")
        })
    if not event.affected_products:
        event.affected_products = sorted({
            str(item["product_id"]) for item in entities if item.get("product_id")
        })
    if not event.affected_warehouses:
        event.affected_warehouses = sorted({
            str(item["warehouse_id"]) for item in entities if item.get("warehouse_id")
        })
    assumption_notes = events.validate_event(event)
    resolved, source = resolve_probability(probability_mode, probability)
    event.probability_mode = probability_mode
    event.probability = resolved
    event.probability_source = source
    assumptions = list(assumption_notes) + [
        f"horizon_days = {horizon_days}. "
        "This value is a scenario assumption and is not an observed historical fact.",
        f"simulation_count = {simulation_count}; random_seed = {random_seed}. "
        "Same inputs plus same seed reproduce the same simulated outcomes.",
    ]
    return SimulationScenario(
        scenario_id=scenario_id,
        name=name or event.name,
        description=description or event.description,
        analysis_date=analysis_date,
        horizon_days=horizon_days,
        event=event,
        affected_entities=list(affected_entities or []),
        probability_mode=probability_mode,
        probability=resolved,
        probability_source=source,
        simulation_count=simulation_count,
        random_seed=random_seed,
        assumptions=assumptions,
        selection_basis=selection_basis,
    )

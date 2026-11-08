"""Shared synthetic inputs for Phase 10 Optimization Engine tests.

Everything here is SYNTHETIC and constructed in memory: no database
session, no real company data, no network access. Tests import these
builders so each optimization test file stays small and readable.

The support layer mirrors the documented Phase 10 input contract: a
Phase 9 replay run built with the NO_ACTION control arm only, plus the
shared baseline entities from ``replay.build_shared_baseline``.
"""

from __future__ import annotations

from typing import Any

from backend.app.analytics.optimization import OptimizationConfig, run_optimization
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod
from backend.app.analytics.simulation.types import SimulationScenario
from backend.app.tests.replay_support import (
    ANALYSIS_DATE,
    HORIZON_DAYS,
    PRODUCTS,
    SUPPLIERS,
    WAREHOUSES,
    make_forecasts,
    make_inputs,
    make_po_lines,
    make_scenario,
    make_shipments,
    make_snapshots,
    make_supplier_links,
    run_replay_for,
)

__all__ = [
    "ANALYSIS_DATE",
    "HORIZON_DAYS",
    "PRODUCTS",
    "SUPPLIERS",
    "WAREHOUSES",
    "build_case",
    "make_forecasts",
    "make_inputs",
    "make_po_lines",
    "make_scenario",
    "make_shipments",
    "make_snapshots",
    "make_supplier_links",
    "run_case",
    "short_outage_scenario",
]


def short_outage_scenario(
    duration_days: int = 3,
    scenario_id: str = "S-SHORT",
    horizon_days: int = HORIZON_DAYS,
) -> SimulationScenario:
    """A supplier outage short enough that S1's order stays eligible.

    The default Phase 9 template outage (14 days, full reduction)
    eliminates S1's 7-day-lead arrival entirely; shortening the window
    keeps the arrival outside the disruption window (arrival day 6) so
    cost-objective scenarios stay feasible for testing.
    """
    event = events_mod.apply_template("SUPPLIER_OUTAGE", "E-SHORT")
    event.duration_days = duration_days
    event.affected_suppliers = ["S1"]
    events_mod.validate_event(event)
    return scenarios_mod.build_scenario(
        scenario_id=scenario_id,
        event=event,
        analysis_date=ANALYSIS_DATE.isoformat(),
        horizon_days=horizon_days,
        affected_entities=targets_mod.resolve_explicit(supplier_ids=["S1"]),
    )


def build_case(
    scenario: SimulationScenario | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One complete Phase 10 input case from public Phase 9 outputs."""
    scenario = scenario or make_scenario()
    inputs = inputs or make_inputs(scenario.horizon_days)
    replay_id = replay_mod.resolve_replay_id(scenario)
    run = run_replay_for(
        [replay_decisions.build_no_action(replay_id)], scenario, inputs,
    )
    entities = replay_mod.build_shared_baseline(
        scenario,
        inputs["forecasts"],
        inputs["snapshots"],
        inputs["shipments"],
        inputs["po_lines"],
        inputs["supplier_links"],
        ANALYSIS_DATE,
    )
    return {
        "run": run,
        "entities": entities,
        "inputs": inputs,
        "scenario": scenario,
    }


def run_case(
    config: OptimizationConfig | None = None,
    case: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run one optimization over a synthetic Phase 10 case."""
    case = case or build_case()
    return run_optimization(
        case["run"],
        case["entities"],
        case["inputs"]["supplier_links"],
        config=config,
        forecast_by_series=case["inputs"]["forecasts"],
        **kwargs,
    )

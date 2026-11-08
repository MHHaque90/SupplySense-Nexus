"""Replay traceability (Phase 9).

Wraps the Phase 8 provenance chain (scenario → event → entity →
supplier/product/warehouse → baseline → forecast → inbound →
simulation) and adds the decision-specific links a reviewer needs to
answer: "Why did this decision produce this outcome?"

Phase 8 traceability is never modified.
"""

from typing import Any

from backend.app.analytics.replay.types import Decision
from backend.app.analytics.simulation import traceability as simulation_trace
from backend.app.analytics.simulation.types import SimulationScenario


def baseline_ref(scenario: SimulationScenario) -> str:
    """Stable identifier of the one shared baseline for this replay."""
    return f"baseline:{scenario.scenario_id}"


def build_decision_trace(
    scenario: SimulationScenario,
    decision: Decision,
    product_id: str,
    warehouse_id: str,
    supplier_ids: list[str],
    forecast_meta: dict[str, Any],
    baseline_on_hand: float,
    inbound_sources: list[str],
) -> dict[str, Any]:
    """Phase 8 trace plus decision_id, type, assumptions, and baseline_ref."""
    trace = simulation_trace.build_trace(
        scenario, product_id, warehouse_id, supplier_ids, forecast_meta,
        baseline_on_hand, inbound_sources,
    )
    trace.update({
        "decision_id": decision.decision_id,
        "decision_type": decision.decision_type,
        "decision_assumptions": list(decision.assumptions),
        "decision_source": decision.source,
        "baseline_ref": baseline_ref(scenario),
        "chain": [
            "scenario", "event", "decision", "supplier/product/warehouse",
            "baseline", "decision_effect", "simulation", "outcome",
        ],
    })
    return trace

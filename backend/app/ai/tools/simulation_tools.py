"""Disruption simulation tool (Phase 8 engine, Phase 11 adapter).

Runs the Monte Carlo disruption simulation for ONE frozen scenario with
the NO_ACTION control arm and returns the full replay report — every value
labeled ``simulated`` and conditional on the declared assumptions.
"""

from typing import Any

from starlette.concurrency import run_in_threadpool

from backend.app.ai.registry import ToolContext
from backend.app.ai.tools import _context as ctx
from backend.app.ai.tools._scenario import prepare_scenario
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.replay import reports as replay_reports
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG

LIMITATIONS = [
    "All outcomes are simulated and conditional on the declared scenario "
    "assumptions; they are not predictions about real operations.",
    "Percentile statistics require enough iterations to be exposed "
    "(configurable minimum in the simulation config).",
]


async def run_disruption_simulation(context: ToolContext) -> dict[str, Any]:
    """Simulate one disruption scenario end to end (compute-only)."""
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=context.params.get("product_id"),
        warehouse_id=context.params.get("warehouse_id"),
        supplier_id=context.params.get("supplier_id"),
    )
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(
        frames, context.params.get("analysis_date")
    )
    bundle = await prepare_scenario(
        context, scope, frames, analysis_date, "sim"
    )
    report = await run_in_threadpool(_simulate, bundle)
    limitations = list(bundle.notes) + LIMITATIONS
    limitations.append(
        "Only the NO_ACTION control arm was simulated; no alternative "
        "decision arms were included."
    )
    return {
        "data": report,
        "source": "simulation_engine",
        "label": str(report.get("data_source_label", "simulated")),
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _simulate(bundle) -> dict[str, Any]:
    """Run the replay engine over the scenario (threadpool-safe, pure CPU)."""
    decision_list = [replay_decisions.build_no_action(bundle.replay_id)]
    run = replay_mod.run_replay(
        bundle.scenario,
        decision_list,
        bundle.forecasts,
        bundle.frames.snapshots,
        bundle.frames.shipments,
        bundle.frames.po_lines,
        bundle.frames.supplier_links,
        bundle.analysis_date,
        DEFAULT_SIMULATION_CONFIG,
        replay_id=bundle.replay_id,
    )
    report = replay_reports.build_report(run)
    report.setdefault("data_source_label", "simulated")
    return report


__all__ = ["run_disruption_simulation"]

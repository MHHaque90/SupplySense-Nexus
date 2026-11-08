"""Optimization analysis tool (Phase 10 engine, Phase 11 adapter).

Thin adapter only: builds the Phase 9 replay context, derives the shared
baseline, calls ``run_optimization`` with one of the FOUR declared
objectives, and returns ``build_report(run)`` — the same audited 21-section
report the CLI produces. Solver statuses (OPTIMAL/FEASIBLE/...) are solver
vocabulary, never advice; outputs are labeled simulated.
"""

from typing import Any

from starlette.concurrency import run_in_threadpool

from backend.app.ai.registry import ToolContext
from backend.app.ai.tools import _context as ctx
from backend.app.ai.tools._scenario import prepare_scenario
from backend.app.analytics.optimization import (
    OptimizationConfig,
    build_report,
    run_optimization,
)
from backend.app.analytics.optimization.types import OBJECTIVES
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG

DEFAULT_TIME_LIMIT_SECONDS = 15
MAX_TIME_LIMIT_SECONDS = 120


def optimization_properties() -> dict[str, dict[str, Any]]:
    """JSON-parameter schema entry for optimization parameters."""
    return {
        "objective": {
            "type": "string",
            "description": (
                "One of: "
                + ", ".join(OBJECTIVES)
                + ". Default minimize_total_cost."
            ),
            "maxLength": 50,
        },
        "shortage_penalty": {
            "type": "number",
            "description": (
                "Required positive shortage penalty per unit for the "
                "cost_shortage_tradeoff objective."
            ),
        },
        "budget": {"type": "number", "description": "Positive budget cap."},
        "min_fulfillment": {
            "type": "number",
            "description": "Minimum fulfillment in [0, 1].",
        },
        "time_limit_seconds": {
            "type": "integer",
            "description": (
                f"Solver time limit 1..{MAX_TIME_LIMIT_SECONDS} "
                f"(default {DEFAULT_TIME_LIMIT_SECONDS})."
            ),
        },
    }


def _build_config(params: dict) -> OptimizationConfig:
    """Validate tool parameters into one OptimizationConfig."""
    objective = str(params.get("objective") or "minimize_total_cost")
    if objective not in OBJECTIVES:
        raise ValueError(
            f"objective must be one of {', '.join(OBJECTIVES)}."
        )
    shortage_penalty = params.get("shortage_penalty")
    if objective == "cost_shortage_tradeoff" and not (
        shortage_penalty is not None and float(shortage_penalty) > 0
    ):
        raise ValueError(
            "objective cost_shortage_tradeoff requires a positive "
            "shortage_penalty."
        )
    budget = params.get("budget")
    if budget is not None and float(budget) <= 0:
        raise ValueError("budget must be positive.")
    min_fulfillment = params.get("min_fulfillment")
    if min_fulfillment is not None and not 0.0 <= float(min_fulfillment) <= 1.0:
        raise ValueError("min_fulfillment must lie in [0, 1].")
    time_limit = int(params.get("time_limit_seconds") or DEFAULT_TIME_LIMIT_SECONDS)
    if not 1 <= time_limit <= MAX_TIME_LIMIT_SECONDS:
        raise ValueError(
            f"time_limit_seconds must be within [1, {MAX_TIME_LIMIT_SECONDS}]."
        )
    return OptimizationConfig(
        objective=objective,
        shortage_penalty_per_unit=float(shortage_penalty)
        if shortage_penalty is not None
        else None,
        budget=float(budget) if budget is not None else None,
        min_fulfillment=float(min_fulfillment)
        if min_fulfillment is not None
        else None,
        time_limit_seconds=time_limit,
    )


async def run_optimization_analysis(context: ToolContext) -> dict[str, Any]:
    """Run the Phase 10 optimization engine and return its full report."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
        supplier_id=params.get("supplier_id"),
    )
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    config = _build_config(params)
    bundle = await prepare_scenario(
        context, scope, frames, analysis_date, "opt"
    )
    report = await run_in_threadpool(_optimize, bundle, config, params)
    status = str(
        (report.get("feasibility_status") or {}).get("status", "UNKNOWN")
    )
    return {
        "data": report,
        "source": "optimization_engine",
        "label": str(report.get("data_source_label", "simulated")),
        "limitations": list(bundle.notes)
        + [
            f"Solver status {status} describes feasibility of the MILP "
            "only; it is not an instruction to act.",
            "Results are simulated planning outputs over synthetic data "
            "with declared assumptions and provenance.",
            f"Objective {config.objective} with solver time limit "
            f"{config.time_limit_seconds}s.",
        ],
        "analysis_date": analysis_date.isoformat(),
    }


def _optimize(bundle, config: OptimizationConfig, params: dict) -> dict[str, Any]:
    """Full Phase 9 -> Phase 10 composition (threadpool-safe, pure CPU)."""
    decision_list = [replay_decisions.build_no_action(bundle.replay_id)]
    replay_run = replay_mod.run_replay(
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
    baseline_entities = replay_mod.build_shared_baseline(
        bundle.scenario,
        bundle.forecasts,
        bundle.frames.snapshots,
        bundle.frames.shipments,
        bundle.frames.po_lines,
        bundle.frames.supplier_links,
        bundle.analysis_date,
    )
    run = run_optimization(
        replay_run,
        baseline_entities,
        bundle.frames.supplier_links,
        config=config,
        forecast_by_series=bundle.forecasts,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
        supplier_id=params.get("supplier_id"),
    )
    report = build_report(run)
    report.setdefault("data_source_label", "simulated")
    return report


__all__ = [
    "DEFAULT_TIME_LIMIT_SECONDS",
    "MAX_TIME_LIMIT_SECONDS",
    "optimization_properties",
    "run_optimization_analysis",
]

"""Optimization endpoint (Phase 12A): Phase 10 solver run, labeled simulated.

Composition mirrors the Phase 11 tool adapter exactly: frozen scenario →
NO_ACTION replay → shared baseline → MILP under ONE declared objective →
full 21-section report. Solver statuses (OPTIMAL/FEASIBLE/...) are solver
vocabulary only — never translated into advice (Phase 11 C2). Compute
POSTs are rate limited and audited.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.ai.ratelimit import RateLimiter, enforce_rate_limit, get_rate_limiter
from backend.app.analytics.optimization import (
    OptimizationConfig,
    build_report,
    run_optimization,
)
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG
from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import PLANNER_PLUS
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import APIError, ErrorCode, success_envelope
from backend.app.core.security import AuthContext, require_roles
from backend.app.schemas.analytics import OptimizationRunRequest

router = APIRouter()


def _build_config(body: OptimizationRunRequest) -> OptimizationConfig:
    """Validate request fields into one Phase 10 solver configuration."""
    if body.objective == "cost_shortage_tradeoff" and not body.shortage_penalty:
        raise ValueError("objective cost_shortage_tradeoff requires a positive shortage_penalty.")
    return OptimizationConfig(
        objective=body.objective,
        shortage_penalty_per_unit=body.shortage_penalty,
        budget=body.budget,
        min_fulfillment=body.min_fulfillment,
        quantity_integrality=body.quantity_integrality,
        time_limit_seconds=float(body.time_limit_seconds),
    )


def _optimize(bundle, config: OptimizationConfig, body) -> dict:
    """Full Phase 9 → Phase 10 composition (threadpool-safe, pure CPU)."""
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
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        supplier_id=body.supplier_id,
    )
    report = build_report(run)
    report.setdefault("data_source_label", "simulated")
    return report


@router.post("/optimization/run")
async def run_optimization_endpoint(
    body: OptimizationRunRequest,
    auth: AuthContext = Depends(require_roles(*PLANNER_PLUS)),
    session: AsyncSession = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Run the Phase 10 MILP for one frozen scenario and declared objective."""
    if not settings.ENABLE_OPTIMIZATION:
        raise APIError(ErrorCode.FEATURE_DISABLED)
    await enforce_rate_limit(session, auth, limiter)
    async with support.map_value_errors():
        config = _build_config(body)
        bundle = await support.prepare_api_scenario(session, auth, body, "api-optimization")
        report = await run_in_threadpool(_optimize, bundle, config, body)
    status = str((report.get("feasibility_status") or {}).get("status", "UNKNOWN"))
    limitations = list(bundle.notes) + [
        f"Solver status {status} describes feasibility of the MILP only; "
        "it is not an instruction to act.",
        "Results are simulated planning outputs over synthetic data with "
        "declared assumptions and provenance.",
        f"Objective {config.objective} with solver time limit {int(config.time_limit_seconds)}s.",
    ]
    await support.audit_run(
        session,
        auth,
        action="optimization.run",
        entity_type="optimization_run",
        entity_id=bundle.scenario.scenario_id,
        parameters={
            "scenario_id": bundle.scenario.scenario_id,
            "replay_id": bundle.replay_id,
            "objective": config.objective,
            "status": status,
            "time_limit_seconds": int(config.time_limit_seconds),
            "horizon_days": bundle.scenario.horizon_days,
        },
    )
    return success_envelope(
        report,
        {
            "data_source_label": "simulated",
            "source": "optimization_engine",
            "analysis_date": bundle.analysis_date.isoformat(),
            "limitations": limitations,
        },
    )


__all__ = ["router"]

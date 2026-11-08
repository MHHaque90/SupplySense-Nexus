"""Disruption simulation endpoints (Phase 12A).

``GET /simulation/events`` exposes the locked Phase 8 event vocabulary
(event types, named templates, probability modes, numeric bounds) so the
frontend never hardcodes them. ``POST /simulation/run`` executes the
Monte Carlo engine over ONE frozen scenario and returns the Phase 8
simulation report — everything labeled ``simulated``, rate limited, and
audited (decision: compute budget is shared across POST endpoints; GET
metadata reads are unlimited).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.ai.ratelimit import RateLimiter, enforce_rate_limit, get_rate_limiter
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import reports as sim_reports
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.analytics.simulation.types import (
    DEFAULT_SIMULATION_CONFIG,
    EVENT_TYPES,
)
from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import ANALYST_PLUS, PLANNER_PLUS
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import APIError, ErrorCode, success_envelope
from backend.app.core.security import AuthContext, require_roles
from backend.app.schemas.analytics import SimulationRunRequest

router = APIRouter()

LIMITATIONS = [
    "All outcomes are simulated and conditional on the declared scenario "
    "assumptions; they are not predictions about real operations.",
    "Percentile statistics require enough iterations to be exposed "
    "(configurable minimum in the simulation config).",
    "Only the NO_ACTION control arm was simulated; no alternative decision arms were included.",
]


@router.get("/simulation/events")
async def read_simulation_events(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
) -> dict:
    """Phase 8 event vocabulary and numeric bounds (static metadata)."""
    return success_envelope(
        {
            "event_types": list(EVENT_TYPES),
            "templates": {
                name: {
                    "event_type": spec.get("event_type"),
                    "description": spec.get("description", ""),
                    "duration_days": spec.get("duration_days"),
                }
                for name, spec in events_mod.TEMPLATES.items()
            },
            "probability_modes": ["deterministic", "explicit", "empirical"],
            "bounds": {
                "horizon_days": {"min": 1, "max": 180, "default": 28},
                "simulation_count": {"min": 1, "max": 500, "default": 20},
                "duration_days": {"min": 1, "max": 365},
                "random_seed_default": 42,
            },
            "notes": [
                "Templates and event types are the locked Phase 8 "
                "contracts; no other event types are supported.",
                "Empirical probability mode is declared but unavailable "
                "(no validated historical disruption-frequency data).",
                "Outcomes are labeled simulated and are never predictions.",
            ],
        },
        {
            "data_source_label": "derived",
            "source": "phase8_event_contract",
        },
    )


def _simulate(bundle) -> dict:
    """Run the Phase 8 simulation engine (threadpool-safe, pure CPU)."""
    result = runner_mod.run_scenario(
        bundle.scenario,
        bundle.forecasts,
        bundle.frames.snapshots,
        bundle.frames.shipments,
        bundle.frames.po_lines,
        bundle.frames.supplier_links,
        bundle.analysis_date,
        DEFAULT_SIMULATION_CONFIG,
    )
    report = sim_reports.build_report(
        bundle.scenario,
        result["baseline"],
        result["scenario"],
        result["deltas"],
        result["traces"],
        DEFAULT_SIMULATION_CONFIG.to_dict(),
    )
    report.setdefault("data_source_label", "simulated")
    return report


@router.post("/simulation/run")
async def run_simulation(
    body: SimulationRunRequest,
    auth: AuthContext = Depends(require_roles(*PLANNER_PLUS)),
    session: AsyncSession = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Run one frozen disruption scenario end to end (compute)."""
    if not settings.ENABLE_SIMULATION:
        raise APIError(ErrorCode.FEATURE_DISABLED)
    await enforce_rate_limit(session, auth, limiter)
    async with support.map_value_errors():
        bundle = await support.prepare_api_scenario(session, auth, body, "api-simulation")
        report = await run_in_threadpool(_simulate, bundle)
    limitations = list(bundle.notes) + LIMITATIONS
    await support.audit_run(
        session,
        auth,
        action="simulation.run",
        entity_type="simulation_run",
        entity_id=bundle.scenario.scenario_id,
        parameters={
            "scenario_id": bundle.scenario.scenario_id,
            "event_type": bundle.scenario.event.event_type,
            "event_template": body.event_template,
            "horizon_days": bundle.scenario.horizon_days,
            "simulation_count": bundle.scenario.simulation_count,
            "random_seed": bundle.scenario.random_seed,
            "probability_mode": bundle.scenario.probability_mode,
        },
    )
    return success_envelope(
        report,
        {
            "data_source_label": "simulated",
            "source": "simulation_engine",
            "analysis_date": bundle.analysis_date.isoformat(),
            "limitations": limitations,
        },
    )


__all__ = ["router"]

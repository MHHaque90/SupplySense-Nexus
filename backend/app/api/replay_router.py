"""Decision Replay Lab endpoints (Phase 12A).

``GET /replay/decisions`` exposes the locked Phase 9 decision vocabulary
and ``max_decisions`` bound. ``POST /replay/run`` replays declared arms
under ONE frozen scenario with the mandatory NO_ACTION control arm and
returns factual deltas only — never a ranking or recommendation
(Phase 11 C2 stays in force). Compute POSTs are rate limited and audited.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.ai.ratelimit import RateLimiter, enforce_rate_limit, get_rate_limiter
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.replay import reports as replay_reports
from backend.app.analytics.replay.types import DECISION_TYPES, DEFAULT_REPLAY_CONFIG
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG
from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import ANALYST_PLUS, PLANNER_PLUS
from backend.app.core.database import get_db
from backend.app.core.errors import success_envelope
from backend.app.core.security import AuthContext, require_roles
from backend.app.schemas.analytics import ReplayRunRequest

router = APIRouter()

LIMITATIONS = [
    "Outcomes are simulated under the declared scenario and decision "
    "assumptions; comparisons are factual deltas with common random "
    "numbers and no ordering of options.",
    "Decision arms are user-declared inputs, never recommendations.",
]


@router.get("/replay/decisions")
async def read_replay_decisions(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
) -> dict:
    """Phase 9 decision vocabulary and replay bounds (static metadata)."""
    return success_envelope(
        {
            "decision_types": list(DECISION_TYPES),
            "max_decisions": DEFAULT_REPLAY_CONFIG.max_decisions,
            "notes": [
                "The NO_ACTION control arm is always present; an empty "
                "decisions request runs only NO_ACTION (baseline outcome, "
                "no comparison claim).",
                "Empty affected_* lists mean org-wide scope; explicit "
                "targets must belong to your organization.",
                "COMBINED_ACTION requires at least one component and "
                "cannot nest inside another COMBINED_ACTION.",
                "Replay results are simulated/illustrative and are never ranked or recommended.",
            ],
        },
        {
            "data_source_label": "derived",
            "source": "phase9_decision_contract",
        },
    )


def _build_decisions(replay_id: str, payloads: list) -> list:
    """Parse declared arms unchanged and force the NO_ACTION control arm."""
    parsed = [
        replay_decisions.decision_from_dict(replay_id, payload.model_dump()) for payload in payloads
    ]
    if not any(decision.decision_type == "NO_ACTION" for decision in parsed):
        parsed.insert(0, replay_decisions.build_no_action(replay_id))
    return parsed


def _replay(bundle, decision_list) -> dict:
    """Run the replay engine (threadpool-safe, pure CPU)."""
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


@router.post("/replay/run")
async def run_replay(
    body: ReplayRunRequest,
    auth: AuthContext = Depends(require_roles(*PLANNER_PLUS)),
    session: AsyncSession = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Replay declared decision arms against the shared baseline."""
    await enforce_rate_limit(session, auth, limiter)
    async with support.map_value_errors():
        bundle = await support.prepare_api_scenario(session, auth, body, "api-replay")
        decision_list = _build_decisions(bundle.replay_id, body.decisions)
        report = await run_in_threadpool(_replay, bundle, decision_list)
    limitations = list(bundle.notes) + LIMITATIONS
    declared = [item for item in decision_list if item.decision_type != "NO_ACTION"]
    if not declared:
        limitations.append(
            "Only the NO_ACTION control arm was run; no decision "
            "comparison exists for this request."
        )
    await support.audit_run(
        session,
        auth,
        action="replay.run",
        entity_type="replay_run",
        entity_id=bundle.scenario.scenario_id,
        parameters={
            "scenario_id": bundle.scenario.scenario_id,
            "replay_id": bundle.replay_id,
            "decision_count": len(decision_list),
            "declared_count": len(body.decisions),
            "horizon_days": bundle.scenario.horizon_days,
            "probability_mode": bundle.scenario.probability_mode,
        },
    )
    return success_envelope(
        report,
        {
            "data_source_label": "simulated",
            "source": "decision_replay_engine",
            "analysis_date": bundle.analysis_date.isoformat(),
            "limitations": limitations,
        },
    )


__all__ = ["router"]

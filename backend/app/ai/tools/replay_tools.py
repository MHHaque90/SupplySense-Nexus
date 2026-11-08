"""Decision replay comparison tool (Phase 9 engine, Phase 11 adapter).

Runs ONE frozen scenario over declared decision arms (the NO_ACTION
control arm is always present) and returns the replay report: factual
decision-vs-baseline and decision-vs-decision deltas under common random
numbers. The engine never ranks or recommends; the tool never invents
decision content — arms come from the request or the offline demo default.

Targeting rule: declared arms may leave ``affected_*`` lists empty. The
engine treats empty targets as org-wide scope (its constraint checks then
report UNCHECKED instead of fabricating supplier-product pairs), and the
Phase 9 validation/constraint pipeline still rejects any explicitly
declared pair or quantity that violates observed constraints.
"""

from typing import Any

from starlette.concurrency import run_in_threadpool

from backend.app.ai.registry import ToolContext
from backend.app.ai.tools import _context as ctx
from backend.app.ai.tools._scenario import prepare_scenario
from backend.app.analytics.replay import decisions as replay_decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.replay import reports as replay_reports
from backend.app.analytics.replay.types import DECISION_TYPES
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG

MAX_DECISIONS = 8

#: Offline default arm used only when the caller declares no decisions.
DEFAULT_DECISIONS: list[dict[str, Any]] = [
    {
        "decision_type": "EXPEDITE_INBOUND",
        "description": "Offline demo arm: expedite inbound units (declared "
        "quantities are illustrative inputs, not recommendations).",
        "quantities": {"expedite_units": 10.0},
        "timing": {"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
        "source": "offline_demo_default",
    }
]


def decision_properties() -> dict[str, dict[str, Any]]:
    """JSON-parameter schema entry for declared decision arms."""
    return {
        "decisions": {
            "type": "array",
            "items": {"type": "object"},
            "description": (
                "Declared decision arms. Each item needs decision_type "
                f"({', '.join(DECISION_TYPES)}) plus optional affected ids, "
                "quantities, timing, and assumptions. Empty affected lists "
                "mean org-wide scope. Default: the offline demo "
                "EXPEDITE_INBOUND arm."
            ),
        }
    }


def _build_decisions(replay_id: str, payloads: list):
    """Parse declared arms unchanged and force the NO_ACTION control arm."""
    parsed = [
        replay_decisions.decision_from_dict(replay_id, payload)
        for payload in payloads
    ]
    if not any(decision.decision_type == "NO_ACTION" for decision in parsed):
        parsed.insert(0, replay_decisions.build_no_action(replay_id))
    return parsed


async def run_decision_comparison(context: ToolContext) -> dict[str, Any]:
    """Replay declared decisions against the shared baseline (simulated)."""
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
        context, scope, frames, analysis_date, "replay"
    )
    payloads = context.params.get("decisions") or list(DEFAULT_DECISIONS)
    if len(payloads) > MAX_DECISIONS:
        raise ValueError(
            f"At most {MAX_DECISIONS} decision arms may be declared per replay."
        )
    decision_list = _build_decisions(bundle.replay_id, payloads)
    report = await run_in_threadpool(_replay, bundle, decision_list)
    limitations = list(bundle.notes) + [
        "Outcomes are simulated under the declared scenario and decision "
        "assumptions; comparisons are factual deltas with common random "
        "numbers and no ordering of options.",
    ]
    declared = [
        item for item in decision_list if item.decision_type != "NO_ACTION"
    ]
    if not declared:
        limitations.append(
            "Only the NO_ACTION control arm was run; no decision comparison "
            "exists for this turn."
        )
    if not context.params.get("decisions"):
        limitations.append(
            "No decisions were declared; the offline demo arm "
            "EXPEDITE_INBOUND (illustrative quantities) was used instead."
        )
    return {
        "data": report,
        "source": "decision_replay_engine",
        "label": str(report.get("data_source_label", "simulated")),
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _replay(bundle, decision_list) -> dict[str, Any]:
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


__all__ = [
    "DEFAULT_DECISIONS",
    "MAX_DECISIONS",
    "decision_properties",
    "run_decision_comparison",
]

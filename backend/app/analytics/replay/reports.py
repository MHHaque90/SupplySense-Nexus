"""Decision Replay Lab reporting: JSON + Markdown (Phase 9).

Exactly twenty-one report sections, no recommendations section. The
report separates HISTORICAL / OBSERVED SYNTHETIC DATA, SCENARIO
ASSUMPTION, DECISION ASSUMPTION, SIMULATED OUTCOME, and
USER_ASSUMED_COST, states that Phase 9 performs no ranking or
optimization, and hands factual outputs to Phase 10.
"""

from typing import Any

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.replay.types import ReplayResult

REPORT_SECTIONS: tuple[str, ...] = (
    "synthetic_data_disclaimer",
    "replay_metadata",
    "disruption_scenario",
    "scenario_assumptions",
    "shared_baseline",
    "decision_definitions",
    "decision_assumptions",
    "decision_validation",
    "simulation_configuration",
    "inventory_outcomes",
    "service_outcomes",
    "supply_outcomes",
    "timing_outcomes",
    "cost_assumptions",
    "cost_outcomes",
    "baseline_comparison",
    "decision_to_decision_comparison",
    "uncertainty",
    "traceability",
    "limitations",
    "phase_10_handoff",
)

SECTION_TITLES: dict[str, str] = {
    "synthetic_data_disclaimer": "Synthetic-data disclaimer",
    "replay_metadata": "Replay metadata",
    "disruption_scenario": "Disruption scenario",
    "scenario_assumptions": "Scenario assumptions",
    "shared_baseline": "Shared baseline",
    "decision_definitions": "Decision definitions",
    "decision_assumptions": "Decision assumptions",
    "decision_validation": "Decision validation",
    "simulation_configuration": "Simulation configuration",
    "inventory_outcomes": "Inventory outcomes",
    "service_outcomes": "Service outcomes",
    "supply_outcomes": "Supply outcomes",
    "timing_outcomes": "Timing outcomes",
    "cost_assumptions": "Cost assumptions",
    "cost_outcomes": "Cost outcomes",
    "baseline_comparison": "Baseline comparison",
    "decision_to_decision_comparison": "Decision-to-decision comparison",
    "uncertainty": "Uncertainty",
    "traceability": "Traceability",
    "limitations": "Limitations",
    "phase_10_handoff": "Phase 10 handoff",
}

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "This analysis uses synthetic/simulated data. Decision assumptions, scenario "
    "assumptions, and simulated outcomes are hypothetical and are not evidence "
    "about real suppliers, real disruptions, or real business operations.",
    "Under the configured disruption scenario, simulated outcomes are conditional "
    "on the event occurring unless an explicit user-assumed probability is stated.",
    "Phase 9 performs factual decision comparison only: it never ranks, never "
    "recommends, never scores, and never selects a decision.",
    "Phase 9 does not optimize. Optimization, search, and solver behavior are "
    "Phase 10 scope.",
    "Missing costs remain None; they are never fabricated or defaulted to zero.",
    "Decision uncertainty (quantities, timing, cost and selection assumptions) is "
    "kept separate from forecast, scenario, and simulation uncertainty.",
    "Point-in-time correctness depends on the analysis date; records dated after "
    "the analysis date are excluded from replay inputs.",
]

PHASE_10_HANDOFF = [
    "Decision contract (Decision with deterministic ids and explicit assumptions).",
    "ReplayResult objects carrying outcomes, baseline deltas, and modeled costs.",
    "Validated constraints with PASS/UNCHECKED notes (failures rejected).",
    "Decision costs: observed purchase cost and USER_ASSUMED_COST values, with "
    "missing costs as None.",
    "Baseline deltas and pairwise decision delta tables (factual arithmetic).",
    "Frozen scenario assumptions and explicit decision assumptions.",
    "Simulation outcomes with separated uncertainty categories.",
    "Traceability chains from scenario to decision effect to outcome.",
    "No optimization API is defined here; Phase 10 defines optimization scope.",
]


def _result_summary(result: ReplayResult) -> dict[str, Any]:
    return {
        "decision_id": result.decision_id,
        "decision_type": result.decision_type,
        "synthetic": result.synthetic,
        "sample_fingerprint": result.sample_fingerprint,
    }


def build_report(replay: dict[str, Any]) -> dict[str, Any]:
    """Assemble the replay report with exactly the 21 required sections."""
    scenario = replay["scenario"]
    event = scenario.get("event") or {}
    baseline = replay["baseline"]
    results: list[ReplayResult] = replay["results"]
    decisions = list(replay.get("decisions", []))
    decision_by_id = {decision.decision_id: decision for decision in decisions}
    outcome_maps = {result.decision_id: result.outcome for result in results}
    inventory = {
        decision_id: {
            "stockout_probability": outcome.get("stockout_probability"),
            "expected_stockout_days": outcome.get("expected_stockout_days"),
            "expected_min_inventory": outcome.get("expected_min_inventory"),
            "expected_ending_inventory": outcome.get("expected_ending_inventory"),
            "inventory_depletion_probability": outcome.get(
                "inventory_depletion_probability"
            ),
        }
        for decision_id, outcome in outcome_maps.items()
    }
    service = {
        decision_id: {
            "expected_unmet_demand": outcome.get("expected_unmet_demand"),
            "service_exposure_probability": outcome.get("service_exposure_probability"),
            "affected_product_count": outcome.get("affected_product_count"),
            "affected_warehouse_count": outcome.get("affected_warehouse_count"),
        }
        for decision_id, outcome in outcome_maps.items()
    }
    supply = {
        decision_id: {
            "affected_supplier_count": outcome.get("affected_supplier_count"),
            "affected_inbound_count": outcome.get("affected_inbound_count"),
            "delayed_inbound_quantity": outcome.get("delayed_inbound_quantity"),
            "unavailable_inbound_quantity": outcome.get("unavailable_inbound_quantity"),
        }
        for decision_id, outcome in outcome_maps.items()
    }
    timing = {
        decision_id: {
            "first_stockout_dates": outcome.get("first_stockout_dates", []),
            "stockout_by_day": outcome.get("stockout_by_day", {}),
        }
        for decision_id, outcome in outcome_maps.items()
    }
    cost_assumptions = {
        result.decision_id: {
            "declared": dict(decision_by_id[result.decision_id].cost_assumptions)
            if result.decision_id in decision_by_id else {},
            "notes": result.decision_cost.get("cost_notes", {}),
        }
        for result in results
    }
    cost_outcomes = {
        result.decision_id: {
            "decision_cost": result.decision_cost.get("decision_cost"),
            "disruption_cost": result.decision_cost.get("disruption_cost"),
            "total_modeled_cost": result.decision_cost.get("total_modeled_cost"),
            "note": (
                "Reported only when observed or user-assumed costs exist; "
                "otherwise None."
            ),
        }
        for result in results
    }
    return {
        "synthetic_data_disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "replay_metadata": {
            "replay_id": replay["replay_id"],
            "scenario_id": replay["scenario_id"],
            "baseline_ref": replay["baseline_ref"],
            "decision_count": len(results),
            "decisions": [_result_summary(result) for result in results],
            "skipped_decisions": replay.get("skipped_decisions", []),
            "synthetic": True,
            "data_source_label": "simulated",
        },
        "disruption_scenario": scenario,
        "scenario_assumptions": {
            "assumptions": scenario.get("assumptions", []),
            "event_assumptions": event.get("assumptions", []),
            "probability": {
                "mode": scenario.get("probability_mode"),
                "value": scenario.get("probability"),
                "source": scenario.get("probability_source"),
            },
            "fingerprint": replay["scenario_fingerprint"],
            "note": (
                "Scenario mechanics are frozen; decision objects cannot modify "
                "event type, probability, duration, reductions, horizon, seed, or "
                "simulation count."
            ),
        },
        "shared_baseline": {
            "baseline_ref": replay["baseline_ref"],
            "outcome": baseline.to_dict(),
            "note": (
                "Built once per entity from historical/observed synthetic data and "
                "shared unchanged by every decision arm."
            ),
        },
        "decision_definitions": [
            _decision_definition(decision, result)
            for result in results
            for decision in [decision_by_id.get(result.decision_id, _MISSING)]
        ],
        "decision_assumptions": {
            result.decision_id: {
                "decision_type": result.decision_type,
                "assumptions": list(
                    decision_by_id[result.decision_id].assumptions
                ) if result.decision_id in decision_by_id else [],
                "effect_notes": list(result.effect_notes),
                "source": decision_by_id[result.decision_id].source
                if result.decision_id in decision_by_id else "user_defined",
            }
            for result in results
        },
        "decision_validation": {
            result.decision_id: {
                "validation": list(result.validation),
                "constraints": list(result.constraint_notes),
            }
            for result in results
        },
        "simulation_configuration": {
            "horizon_days": scenario.get("horizon_days"),
            "simulation_count": scenario.get("simulation_count"),
            "random_seed": scenario.get("random_seed"),
            "analysis_date": scenario.get("analysis_date"),
            "config": replay["simulation_config"],
            "replay_config": replay["replay_config"],
            "sample_fingerprint": replay["sample_fingerprint"],
            "note": (
                "One seeded generator samples the scenario distributions once; the "
                "same sampled parameter arrays feed every decision arm."
            ),
        },
        "inventory_outcomes": inventory,
        "service_outcomes": service,
        "supply_outcomes": supply,
        "timing_outcomes": timing,
        "cost_assumptions": cost_assumptions,
        "cost_outcomes": cost_outcomes,
        "baseline_comparison": {
            "semantics": "decision arm minus shared baseline (factual arithmetic).",
            "deltas": replay["baseline_deltas"],
        },
        "decision_to_decision_comparison": {
            "semantics": (
                "right decision minus left decision (factual arithmetic); no "
                "ranking, no scores, no selection."
            ),
            "pairs": replay["pairwise"],
        },
        "uncertainty": replay["uncertainty"],
        "traceability": {
            result.decision_id: list(result.traceability.get("entities", []))
            for result in results
        },
        "limitations": list(REPORT_LIMITATIONS),
        "phase_10_handoff": list(PHASE_10_HANDOFF),
    }


class _MissingDecision:
    """Placeholder when a result has no matching decision object."""

    decision_id = ""
    decision_type = "UNKNOWN"
    description = ""
    affected_suppliers: list[str] = []
    affected_products: list[str] = []
    affected_warehouses: list[str] = []
    quantities: dict[str, float] = {}
    timing: dict[str, int] = {}
    cost_assumptions: dict[str, float] = {}
    assumptions: list[str] = []
    source = "user_defined"


_MISSING = _MissingDecision()


def _decision_definition(decision: Any, result: ReplayResult) -> dict[str, Any]:
    return {
        "decision_id": result.decision_id,
        "decision_type": decision.decision_type,
        "description": decision.description,
        "affected_suppliers": list(decision.affected_suppliers),
        "affected_products": list(decision.affected_products),
        "affected_warehouses": list(decision.affected_warehouses),
        "quantities": dict(decision.quantities),
        "timing": dict(decision.timing),
        "cost_assumptions": dict(decision.cost_assumptions),
        "source": decision.source,
        "data_label": "DECISION_ASSUMPTION",
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the replay report as Markdown with all 21 sections."""
    metadata = report["replay_metadata"]
    lines = [
        "# SupplySense Nexus Decision Replay Lab Report",
        "",
        f"_{report['synthetic_data_disclaimer']}_",
        "",
        f"Replay: {metadata['replay_id']} under scenario {metadata['scenario_id']} "
        f"(shared baseline {metadata['baseline_ref']}).",
        "",
    ]
    for index, section in enumerate(REPORT_SECTIONS, start=1):
        title = SECTION_TITLES[section]
        lines.append(f"## {index}. {title}")
        lines.extend(_render_section(section, report))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_section(section: str, report: dict[str, Any]) -> list[str]:
    payload = report[section]
    if section == "synthetic_data_disclaimer":
        return [f"- {payload}"]
    if section == "replay_metadata":
        lines = [
            f"- replay_id: {payload['replay_id']}",
            f"- scenario_id: {payload['scenario_id']}",
            f"- shared baseline: {payload['baseline_ref']}",
            f"- decision arms: {payload['decision_count']}",
        ]
        for item in payload["decisions"]:
            lines.append(
                f"- arm: {item['decision_id']} ({item['decision_type']}) — "
                "decision assumption, synthetic data."
            )
        return lines
    if section == "disruption_scenario":
        event = payload.get("event") or {}
        return [
            f"- scenario_id: {payload.get('scenario_id')}",
            f"- event: {event.get('event_type')} ({event.get('event_id')})",
            f"- analysis date: {payload.get('analysis_date')}; "
            f"horizon: {payload.get('horizon_days')} days",
            "- Under the configured disruption scenario the event mechanics are "
            "frozen for every decision arm (scenario assumption).",
        ]
    if section == "scenario_assumptions":
        lines = [f"- {note}" for note in payload.get("assumptions", [])]
        probability = payload["probability"]
        lines.append(
            f"- probability mode={probability['mode']}, value={probability['value']}, "
            f"source={probability['source']} (scenario assumption)."
        )
        lines.append(f"- {payload['note']}")
        return lines
    if section == "shared_baseline":
        outcome = payload["outcome"]
        return [
            f"- baseline_ref: {payload['baseline_ref']}",
            f"- stockout probability {outcome['stockout_probability']}, "
            f"expected unmet demand {outcome['expected_unmet_demand']}, "
            f"expected ending inventory {outcome['expected_ending_inventory']}",
            f"- {payload['note']}",
        ]
    if section == "decision_definitions":
        return [
            f"- {item['decision_id']}: {item['decision_type']} "
            f"(source={item['source']}, label={item['data_label']})"
            for item in payload
        ]
    if section == "decision_assumptions":
        lines = []
        for decision_id, item in payload.items():
            lines.append(f"- {decision_id} ({item['decision_type']}):")
            for note in item["assumptions"]:
                lines.append(f"  - assumption: {note}")
            for note in item["effect_notes"]:
                lines.append(f"  - effect: {note}")
        return lines or ["- No decision assumptions recorded."]
    if section == "decision_validation":
        lines = []
        for decision_id, item in payload.items():
            lines.append(f"- {decision_id}: validation {len(item['validation'])} note(s), "
                         f"constraints {len(item['constraints'])} note(s).")
            for note in item["constraints"]:
                lines.append(f"  - {note}")
        return lines
    if section == "simulation_configuration":
        return [
            f"- horizon_days: {payload['horizon_days']}",
            f"- simulation_count: {payload['simulation_count']}",
            f"- random_seed: {payload['random_seed']}",
            f"- sample_fingerprint: {payload['sample_fingerprint']}",
            f"- {payload['note']}",
        ]
    if section in (
        "inventory_outcomes", "service_outcomes", "supply_outcomes",
    ):
        lines = []
        for decision_id, item in payload.items():
            rendered = ", ".join(f"{key}={value}" for key, value in item.items())
            lines.append(f"- {decision_id}: {rendered} (simulated outcome).")
        return lines
    if section == "timing_outcomes":
        lines = []
        for decision_id, item in payload.items():
            lines.append(
                f"- {decision_id}: first stockout dates {item['first_stockout_dates']}; "
                f"{item['stockout_by_day']} (simulated outcome)."
            )
        return lines
    if section == "cost_assumptions":
        lines = []
        for decision_id, item in payload.items():
            lines.append(
                f"- {decision_id}: declared costs {item['declared'] or 'None'}; "
                f"provenance {item['notes'] or 'None'}."
            )
        return lines or ["- No cost assumptions declared."]
    if section == "cost_outcomes":
        lines = []
        for decision_id, item in payload.items():
            lines.append(
                f"- {decision_id}: decision_cost={item['decision_cost']}, "
                f"disruption_cost={item['disruption_cost']}, "
                f"total_modeled_cost={item['total_modeled_cost']} "
                "(user-assumed or observed synthetic cost)."
            )
            lines.append(f"  - {item['note']}")
        return lines
    if section == "baseline_comparison":
        lines = [f"- semantics: {payload['semantics']}"]
        for decision_id, deltas in payload["deltas"].items():
            for key, value in sorted(deltas.items()):
                lines.append(f"- {decision_id} {key}: {value}")
        return lines
    if section == "decision_to_decision_comparison":
        lines = [f"- semantics: {payload['semantics']}"]
        for pair in payload["pairs"]:
            lines.append(
                f"- {pair['right_decision_id']} minus "
                f"{pair['left_decision_id']}:"
            )
            for key, value in sorted(pair["deltas"].items()):
                lines.append(f"  - {key}: {value}")
        return lines or ["- Only one decision arm; pairwise comparison needs two."]
    if section == "uncertainty":
        lines = [
            f"- forecast uncertainty: {payload['forecast_uncertainty']['note']}",
            f"- scenario uncertainty: {payload['scenario_uncertainty']['note']}",
            f"- simulation variability: {payload['simulation_variability']['note']}",
            f"- decision uncertainty: {payload['decision_uncertainty']['note']}",
        ]
        for item in payload["decision_uncertainty"]["decisions"]:
            lines.append(
                f"  - {item['decision_id']}: quantities={item['quantities']}, "
                f"timing={item['timing']}, costs={item['cost_assumptions']}"
            )
        return lines
    if section == "traceability":
        lines = []
        for decision_id, traces in payload.items():
            for trace in traces:
                lines.append(
                    f"- {decision_id}: scenario {trace['scenario_id']} → event "
                    f"{trace['event_type']} → decision {trace['decision_type']} → "
                    f"{trace['product_id']}|{trace['warehouse_id']} → baseline "
                    f"{trace['baseline_ref']} → simulation → outcome."
                )
        return lines or ["- No traceability entries recorded."]
    if section == "limitations":
        return [f"- {item}" for item in payload]
    if section == "phase_10_handoff":
        return [f"- {item}" for item in payload]
    return []

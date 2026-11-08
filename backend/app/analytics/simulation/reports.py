"""Disruption simulation reporting: JSON + Markdown (Phase 8).

Every report separates HISTORICAL OBSERVATION, SCENARIO ASSUMPTION,
and SIMULATED OUTCOME, and forecast uncertainty, scenario
uncertainty, and simulation variability each get their own section.
No recommendations section exists.
"""

from typing import Any

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.simulation.types import ScenarioOutcome, SimulationScenario

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "This analysis uses synthetic/simulated data. Scenario assumptions and simulation outcomes are hypothetical and are not evidence about real suppliers, real disruptions, or real business operations.",
    "Simulated outcomes are conditional on the event occurring unless an explicit user-assumed probability is stated.",
    "Intervals describe in-sample backtest dispersion, not guarantees.",
    "Empirical coverage on synthetic data does not imply future real-world coverage.",
    "Risk severity was never converted into event probability.",
    "No empirical disruption-frequency data exists; empirical mode is unavailable.",
]


def build_report(
    scenario: SimulationScenario,
    baseline: ScenarioOutcome,
    outcome: ScenarioOutcome,
    deltas: dict[str, float | None],
    traces: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the full simulation report with all required sections."""
    event = scenario.event
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "scenario_definition": scenario.to_dict(),
        "event_type": event.event_type if event else None,
        "event_assumptions": event.assumptions if event else [],
        "probability_mode": scenario.probability_mode,
        "probability_provenance": {
            "mode": scenario.probability_mode,
            "probability": scenario.probability,
            "source": scenario.probability_source,
        },
        "baseline_definition": {
            "source": scenario.baseline_source,
            "note": "Historical observation: current inventory, selected forecast, known inbound.",
        },
        "simulation_configuration": {
            "horizon_days": scenario.horizon_days,
            "simulation_count": scenario.simulation_count,
            "random_seed": scenario.random_seed,
            "config": config,
        },
        "affected_entities": scenario.affected_entities,
        "inventory_outcomes": outcome.to_dict(),
        "service_outcomes": {
            "service_exposure_probability": outcome.service_exposure_probability,
            "expected_unmet_demand": outcome.expected_unmet_demand,
            "median_unmet_demand": outcome.median_unmet_demand,
            "p90_unmet_demand": outcome.p90_unmet_demand,
            "p95_unmet_demand": outcome.p95_unmet_demand,
            "affected_product_count": outcome.affected_product_count,
            "affected_warehouse_count": outcome.affected_warehouse_count,
        },
        "supply_outcomes": {
            "affected_supplier_count": outcome.affected_supplier_count,
            "affected_supplier_product_count": outcome.affected_supplier_product_count,
            "affected_inbound_count": outcome.affected_inbound_count,
            "delayed_inbound_quantity": outcome.delayed_inbound_quantity,
            "unavailable_inbound_quantity": outcome.unavailable_inbound_quantity,
        },
        "stockout_distribution": {
            "stockout_by_day": outcome.stockout_by_day,
            "first_stockout_dates": outcome.first_stockout_dates,
            "expected_stockout_days": outcome.expected_stockout_days,
        },
        "unmet_demand_distribution": outcome.distributions.get("unmet_demand", {}),
        "baseline_outcome": baseline.to_dict(),
        "scenario_outcome": outcome.to_dict(),
        "delta": deltas,
        "forecast_uncertainty": {
            "note": "Inherited from Phase 4 intervals; not recalculated here.",
        },
        "scenario_uncertainty": {
            "distributions": [item.to_dict() for item in event.distributions] if event else [],
            "note": "Only explicitly configured parameters vary across iterations.",
        },
        "simulation_variability": {
            "random_seed": scenario.random_seed,
            "simulation_count": scenario.simulation_count,
            "note": "Same inputs plus same seed reproduce the same simulated outcomes.",
        },
        "traceability": traces,
        "limitations": REPORT_LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as human-readable Markdown (analytical wording)."""
    scenario = report["scenario_definition"]
    delta = report["delta"]
    lines = [
        "# SupplySense Nexus Disruption Simulation Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Scenario: {scenario['scenario_id']} ({scenario['event']['event_type']})",
        f"Analysis date: {scenario['analysis_date']}; "
        f"horizon: {scenario['horizon_days']} days; "
        f"iterations: {scenario['simulation_count']}; seed: {scenario['random_seed']}",
        "",
        "## Scenario definition (scenario assumption)",
        f"- {scenario['description']}",
        "",
        "## Event type (scenario assumption)",
        f"- {scenario['event']['event_type']}: {scenario['event']['description']}",
        "",
        "## Event assumptions (scenario assumptions, not observed facts)",
    ]
    for assumption in scenario["event"]["assumptions"]:
        lines.append(f"- {assumption}")
    lines += ["", "## Probability mode (scenario assumption)"]
    provenance = report["probability_provenance"]
    lines.append(
        f"- mode={provenance['mode']}, probability={provenance['probability']}, "
        f"source={provenance['source']}"
    )
    lines += ["", "## Probability provenance (scenario assumption)"]
    lines.append("- Risk severity is never converted into event probability.")
    lines += ["", "## Baseline definition (historical observation)"]
    lines.append(f"- {report['baseline_definition']['note']}")
    lines += ["", "## Simulation configuration (scenario assumption)"]
    lines.append(
        f"- horizon={report['simulation_configuration']['horizon_days']}, "
        f"count={report['simulation_configuration']['simulation_count']}, "
        f"seed={report['simulation_configuration']['random_seed']}"
    )
    lines += ["", "## Affected entities (scenario assumption)"]
    for entity in scenario["affected_entities"][:15]:
        lines.append(f"- {entity}")
    lines += ["", "## Inventory outcomes (simulated outcome)"]
    outcome = report["scenario_outcome"]
    lines.append(
        f"- stockout probability {outcome['stockout_probability']}, "
        f"expected stockout days {outcome['expected_stockout_days']}, "
        f"expected ending inventory {outcome['expected_ending_inventory']}"
    )
    lines += ["", "## Service outcomes (simulated outcome)"]
    service = report["service_outcomes"]
    lines.append(
        f"- expected unmet demand {service['expected_unmet_demand']}, "
        f"median {service['median_unmet_demand']}, "
        f"p90 {service['p90_unmet_demand']}, p95 {service['p95_unmet_demand']}"
    )
    lines += ["", "## Supply outcomes (simulated outcome)"]
    supply = report["supply_outcomes"]
    lines.append(
        f"- affected suppliers {supply['affected_supplier_count']}, "
        f"delayed inbound {supply['delayed_inbound_quantity']}, "
        f"unavailable inbound {supply['unavailable_inbound_quantity']}"
    )
    lines += ["", "## Stockout distribution (simulated outcome)"]
    for key, value in outcome["stockout_by_day"].items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Unmet-demand distribution (simulated outcome)"]
    for key, value in sorted(report["unmet_demand_distribution"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## Baseline vs scenario (simulated outcome)"]
    for key, value in sorted(delta.items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## Forecast uncertainty (historical observation)"]
    lines.append("- Inherited from Phase 4 intervals; not recalculated here.")
    lines += ["", "## Scenario uncertainty (scenario assumption)"]
    for item in report["scenario_uncertainty"]["distributions"]:
        lines.append(
            f"- {item['parameter']}: {item['distribution']} "
            f"(min={item['minimum']}, mode={item['mode']}, max={item['maximum']} "
            f"{item['units']}, source={item['source']})"
        )
    if not report["scenario_uncertainty"]["distributions"]:
        lines.append("- No sampled parameters; deterministic scenario.")
    lines += ["", "## Simulation variability (simulated outcome)"]
    lines.append(
        f"- seed={report['simulation_variability']['random_seed']}, "
        f"count={report['simulation_variability']['simulation_count']}"
    )
    lines += ["", "## Traceability (historical observation + assumptions)"]
    for trace in report["traceability"][:15]:
        lines.append(
            f"- {trace['product_id']}|{trace['warehouse_id']}: "
            f"model {trace['forecast_model']}, suppliers {trace['supplier_ids']}"
        )
    lines += ["", "## Limitations"]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines += ["", "## Phase 9 handoff (contracts, not decisions)"]
    lines.append("Scenario definition, event assumptions, baseline, simulated outcomes, "
                 "stockout probability, service impact, unmet demand, inventory impact, "
                 "supplier exposure, affected products/warehouses, uncertainty, probability "
                 "provenance, seed, count, and traceability are available for Decision Replay.")
    return "\n".join(lines) + "\n"

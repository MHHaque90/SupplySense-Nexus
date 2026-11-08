"""Phase 8 report assembly tests (structure, labeling, wording)."""

from backend.app.analytics.simulation import reports
from backend.app.analytics.simulation.types import (
    DisruptionEvent,
    ScenarioOutcome,
    SimulationScenario,
)


def _scenario():
    return SimulationScenario(
        scenario_id="S1", name="Test outage", analysis_date="2026-06-30",
        horizon_days=14,
        event=DisruptionEvent(
            event_id="E1", event_type="SUPPLIER_DISRUPTION", name="Outage",
            duration_days=14, supply_reduction=1.0,
            affected_suppliers=["S1"],
            assumptions=["duration_days = 14. assumption note."],
        ),
        affected_entities=[{"entity_type": "supplier", "supplier_id": "S1"}],
        simulation_count=50, random_seed=7,
    )


def _outcome(label):
    outcome = ScenarioOutcome(label=label)
    outcome.stockout_probability = 0.2 if label == "scenario" else 0.0
    outcome.expected_unmet_demand = 15.0 if label == "scenario" else 0.0
    return outcome


def test_report_json_structure_and_labeling():
    scenario = _scenario()
    report = reports.build_report(
        scenario, _outcome("baseline"), _outcome("scenario"),
        {"delta_stockout_probability": 0.2}, [], {"default_horizon_days": 28},
    )
    assert "SYNTHETIC" in report["disclaimer"]
    assert report["synthetic"] is True
    assert report["event_type"] == "SUPPLIER_DISRUPTION"
    assert report["probability_mode"] == "deterministic"
    assert report["probability_provenance"]["source"] == "DETERMINISTIC"
    assert report["delta"]["delta_stockout_probability"] == 0.2
    assert len(report["limitations"]) >= 5


def test_markdown_sections_and_wording():
    scenario = _scenario()
    report = reports.build_report(
        scenario, _outcome("baseline"), _outcome("scenario"), {},
        [{"scenario_id": "S1", "event_id": "E1", "event_type": "SUPPLIER_DISRUPTION",
          "product_id": "P1", "warehouse_id": "W1", "supplier_ids": ["S1"],
          "baseline_on_hand": 100.0, "forecast_model": "holt",
          "forecast_origin": "2026-06-30", "forecast_horizon": 14,
          "inbound_sources": ["PO1"], "probability_mode": "deterministic",
          "probability_source": "DETERMINISTIC", "random_seed": 7,
          "simulation_count": 50, "selection_basis": "explicit_user_selection",
          "data_source_label": "simulated"}],
        {},
    )
    markdown = reports.render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Disruption Simulation Report")
    assert "SYNTHETIC" in markdown
    for section in ("Scenario definition", "Event type", "Event assumptions",
                    "Probability mode", "Probability provenance",
                    "Baseline definition", "Simulation configuration",
                    "Affected entities", "Inventory outcomes", "Service outcomes",
                    "Supply outcomes", "Stockout distribution",
                    "Unmet-demand distribution", "Baseline vs scenario",
                    "Forecast uncertainty", "Scenario uncertainty",
                    "Simulation variability", "Traceability", "Limitations",
                    "Phase 9 handoff"):
        assert section in markdown
    lowered = markdown.lower()
    for banned in ("will happen", "will occur", "guaranteed", "predicted disruption",
                   "certain supplier failure", "should switch", "order more",
                   "best supplier", "optimal quantity"):
        assert banned not in lowered
    assert "## Recommendations" not in markdown

"""Phase 10 point-in-time (future-data) leakage tests (spec section 25.F).

Records dated after the analysis date must never influence the input
adapter, the formulation, the solver result, or the report.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from backend.app.analytics.optimization import OptimizationConfig, build_report
from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.tests.optimization_support import (
    ANALYSIS_DATE,
    build_case,
    run_case,
    short_outage_scenario,
)

FUTURE = date(2027, 1, 1)
OBJECTIVE = OptimizationConfig(objective="minimize_total_cost")


def _inputs_with_future_records():
    """Synthetic inputs polluted with post-analysis-date records."""
    inputs = build_case(short_outage_scenario())["inputs"]
    future_snapshot = pd.DataFrame([{
        "snapshot_date": FUTURE,
        "organization_id": "ORG1",
        "product_id": "P1",
        "warehouse_id": "W1",
        "on_hand": 9999.0,
        "reserved": 0.0,
        "in_transit": 0.0,
        "sku": "SKU-P1",
        "unit_cost": 10.0,
    }])
    future_po = pd.DataFrame([{
        "po_id": "PO9", "po_number": "PO-9", "organization_id": "ORG1",
        "supplier_id": "S1", "supplier_name": "Alpha", "product_id": "P1",
        "order_date": FUTURE, "expected_delivery_date": date(2027, 1, 20),
        "quantity": 5000.0, "unit_cost": 12.5, "line_total": 62500.0,
        "moq": 10.0, "lead_time_days": 7, "status": "open",
    }])
    future_shipment = pd.DataFrame([{
        "shipment_id": "SH9", "po_id": "PO9", "supplier_id": "S1",
        "supplier_name": "Alpha", "shipped_date": FUTURE,
        "expected_arrival_date": date(2027, 1, 20),
        "actual_arrival_date": None, "status": "in_transit", "delay_days": None,
    }])
    dirty = dict(inputs)
    dirty["snapshots"] = pd.concat(
        [inputs["snapshots"], future_snapshot], ignore_index=True)
    dirty["po_lines"] = pd.concat(
        [inputs["po_lines"], future_po], ignore_index=True)
    dirty["shipments"] = pd.concat(
        [inputs["shipments"], future_shipment], ignore_index=True)
    return dirty


def _clean_case():
    return build_case(short_outage_scenario())


def _dirty_case():
    return build_case(
        short_outage_scenario(), inputs=_inputs_with_future_records(),
    )


def test_future_records_do_not_change_the_input_adapter():
    clean = _clean_case()
    dirty = _dirty_case()
    clean_inputs = inputs_mod.build_optimization_inputs(
        clean["run"], clean["entities"], clean["inputs"]["supplier_links"],
    )
    dirty_inputs = inputs_mod.build_optimization_inputs(
        dirty["run"], dirty["entities"], dirty["inputs"]["supplier_links"],
    )
    assert [entity.demand for entity in dirty_inputs.entities] == [
        entity.demand for entity in clean_inputs.entities
    ]
    assert [entity.existing_inbound for entity in dirty_inputs.entities] == [
        entity.existing_inbound for entity in clean_inputs.entities
    ]
    assert dirty_inputs.offers == clean_inputs.offers
    assert dirty_inputs.provenance.to_dict() == clean_inputs.provenance.to_dict()


def test_future_records_do_not_change_problem_id_or_decisions():
    clean = run_case(config=OBJECTIVE, case=_clean_case())
    dirty = run_case(config=OBJECTIVE, case=_dirty_case())
    assert dirty["problem"]["problem_id"] == clean["problem"]["problem_id"]
    assert dirty["result"]["decision_values"] == clean["result"]["decision_values"]
    assert dirty["result"]["objective_value"] == clean["result"]["objective_value"]


def test_future_records_do_not_change_the_report():
    clean_run = run_case(config=OBJECTIVE, case=_clean_case())
    dirty_run = run_case(config=OBJECTIVE, case=_dirty_case())
    for run in (clean_run, dirty_run):
        run["timings"] = {}
    clean_report = build_report(clean_run)
    dirty_report = build_report(dirty_run)
    clean_report["optimization_run_metadata"]["timings_seconds"] = {}
    dirty_report["optimization_run_metadata"]["timings_seconds"] = {}
    assert clean_report == dirty_report


def test_report_records_the_analysis_date_for_point_in_time_scope():
    run = run_case(config=OBJECTIVE, case=_clean_case())
    report = build_report(run)
    assert report["optimization_run_metadata"]["analysis_date"] == (
        ANALYSIS_DATE.isoformat()
    )
    assert report["provenance"]["analysis_date"] == ANALYSIS_DATE.isoformat()
    limitations = " ".join(report["limitations"])
    assert "Orders arriving after the horizon are out of scope" in limitations


def test_demand_forecast_origin_is_not_after_analysis_date():
    run = run_case(config=OBJECTIVE, case=_clean_case())
    references = run["problem"]["provenance"]["forecast_references"]
    assert references
    for reference in references:
        origin = date.fromisoformat(reference["origin"])
        assert origin <= ANALYSIS_DATE

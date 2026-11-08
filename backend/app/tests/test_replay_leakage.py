"""Phase 9 point-in-time (future-data) leakage tests.

Records dated after the analysis date must never influence the shared
baseline, any decision arm, or the report.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.replay import decisions, reports
from backend.app.tests.replay_support import (
    ANALYSIS_DATE,
    make_inputs,
    make_scenario,
    run_replay_for,
)

FUTURE = date(2027, 1, 1)


def _arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "EXPEDITE_INBOUND",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"expedite_units": 30.0},
            timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
        ),
    ]


def _inputs_with_future_records():
    """Synthetic inputs polluted with post-analysis-date records."""
    inputs = make_inputs()
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
    inputs["snapshots"] = pd.concat(
        [inputs["snapshots"], future_snapshot], ignore_index=True)
    inputs["po_lines"] = pd.concat(
        [inputs["po_lines"], future_po], ignore_index=True)
    inputs["shipments"] = pd.concat(
        [inputs["shipments"], future_shipment], ignore_index=True)
    return inputs


def test_future_snapshot_does_not_change_the_shared_baseline():
    scenario = make_scenario()
    clean = run_replay_for(_arms(), scenario, make_inputs())
    dirty = run_replay_for(_arms(), scenario, _inputs_with_future_records())
    assert dirty["baseline"].to_dict() == clean["baseline"].to_dict()


def test_future_inbound_records_do_not_change_any_arm():
    scenario = make_scenario()
    clean = run_replay_for(_arms(), scenario, make_inputs())
    dirty = run_replay_for(_arms(), scenario, _inputs_with_future_records())
    assert [result.to_dict() for result in dirty["results"]] == [
        result.to_dict() for result in clean["results"]
    ]
    assert dirty["sample_fingerprint"] == clean["sample_fingerprint"]


def test_future_records_do_not_change_the_report():
    scenario = make_scenario()
    clean = reports.build_report(
        run_replay_for(_arms(), scenario, make_inputs()))
    dirty = reports.build_report(
        run_replay_for(_arms(), scenario, _inputs_with_future_records()))
    assert clean == dirty


def test_report_records_the_analysis_date_for_point_in_time_scope():
    run = run_replay_for(_arms())
    assert run["scenario"]["analysis_date"] == ANALYSIS_DATE.isoformat()
    report = reports.build_report(run)
    configuration = report["simulation_configuration"]
    assert configuration["analysis_date"] == ANALYSIS_DATE.isoformat()
    limitations = " ".join(report["limitations"])
    assert "records dated after the analysis date are excluded" in limitations

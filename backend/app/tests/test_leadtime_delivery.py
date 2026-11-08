"""Phase 6 lead-time and delivery classification tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement import delivery, lead_times
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG

ANALYSIS = date(2026, 6, 30)
CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _shipments(delays, supplier="S1"):
    base = date(2026, 3, 1)
    return pd.DataFrame({
        "shipment_id": [f"SH{i}" for i in range(len(delays))],
        "po_id": [f"PO{i}" for i in range(len(delays))],
        "supplier_id": [supplier] * len(delays),
        "expected_arrival_date": [base] * len(delays),
        "actual_arrival_date": [
            date.fromordinal(base.toordinal() + delay) for delay in delays
        ],
        "delay_days": [float(delay) for delay in delays],
    })


def _lines_for(count):
    return pd.DataFrame({
        "po_id": [f"PO{i}" for i in range(count)],
        "supplier_id": ["S1"] * count,
        "product_id": ["P1"] * count,
        "order_date": [date(2026, 1, 1)] * count,
        "quantity": [10.0] * count,
        "status": ["received"] * count,
    })


def test_lead_time_statistics():
    shipments = _shipments([0, 2, 4])
    result = lead_times.describe_relationship_lead_time(
        "S1", "P1", _lines_for(3), shipments, 12.0, ANALYSIS, CONFIG
    )
    assert result.observations == 3
    assert result.contracted_days == 12.0
    assert result.average_observed_days is not None
    assert result.min_observed_days is not None
    assert result.max_observed_days is not None
    assert result.delay_frequency is not None
    assert 0.0 <= result.delay_frequency <= 1.0


def test_percentiles_need_minimum_observations():
    result = lead_times.describe_relationship_lead_time(
        "S1", "P1", _lines_for(2), _shipments([0, 1]), None, ANALYSIS, CONFIG
    )
    assert result.percentiles == {}
    result = lead_times.describe_relationship_lead_time(
        "S1", "P1", _lines_for(5), _shipments([0, 1, 2, 3, 4]), None, ANALYSIS, CONFIG
    )
    assert set(result.percentiles) == {"p25", "p50", "p75", "p90"}
    assert result.percentiles["p25"] <= result.percentiles["p90"]


def test_no_observations_explicit():
    result = lead_times.describe_relationship_lead_time(
        "SX", "P1", _lines_for(2), _shipments([0, 1]), 9.0, ANALYSIS, CONFIG
    )
    assert result.observations == 0
    assert result.average_observed_days is None
    assert result.contracted_days == 9.0


def test_reliability_unknown_below_minimum():
    result = delivery.describe_delivery("S1", _shipments([0, 1]), ANALYSIS, CONFIG)
    assert result.reliability == "UNKNOWN"
    assert "delivered_shipment_history" in result.missing_evidence


def test_reliability_stable_boundary():
    result = delivery.describe_delivery("S1", _shipments([0, 0, 0, 0, 0]), ANALYSIS, CONFIG)
    assert result.reliability == "STABLE"
    assert result.on_time_rate == 1.0


def test_reliability_high_delay_boundary():
    result = delivery.describe_delivery(
        "S1", _shipments([0, 0, 5, 6, 7]), ANALYSIS, CONFIG
    )
    assert result.reliability == "HIGH_DELAY"
    assert result.late_rate == 0.6


def test_reliability_delayed_boundary():
    result = delivery.describe_delivery(
        "S1", _shipments([0, 0, 0, 0, 3, 0, 0, 0, 0, 0]), ANALYSIS, CONFIG
    )
    assert result.reliability == "DELAYED"
    assert result.evidence and result.missing_evidence == []


def test_reliability_variable_spread():
    result = delivery.describe_delivery(
        "S1", _shipments([0, 0, 0, 0, 0, 0, 0, 0, 0, 20]), ANALYSIS, CONFIG
    )
    # Late rate 0.1 below delayed cutoff but spread above variability cutoff.
    assert result.reliability == "VARIABLE"

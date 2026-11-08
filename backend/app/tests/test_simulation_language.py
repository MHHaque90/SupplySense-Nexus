"""Phase 8 output language safety tests."""

from backend.app.analytics.simulation import events, probability
from backend.app.analytics.simulation.types import DisruptionEvent


def test_no_predictive_language_in_event_text():
    event = DisruptionEvent(
        event_id="E1", event_type="SUPPLIER_DISRUPTION", name="Outage",
        duration_days=14, supply_reduction=1.0, affected_suppliers=["S1"],
    )
    text = (events.describe_event(event) + " " + " ".join(event.assumptions)).lower()
    for banned in ("will happen", "will occur", "guaranteed", "predicted disruption",
                   "certain supplier failure"):
        assert banned not in text


def test_no_decision_or_optimization_language():
    from backend.app.analytics.simulation import reports

    text = " ".join(reports.REPORT_LIMITATIONS).lower()
    for banned in ("order more", "best supplier", "optimal", "should switch",
                   "expedite", "replay"):
        assert banned not in text


def test_probability_language_not_predictive():
    text = probability.describe_probability("explicit", 0.2, "USER_ASSUMED")
    assert "20%" in text and "user-assumed" in text
    assert "not predicted or empirically validated" in text
    deterministic = probability.describe_probability("deterministic", 1.0, "DETERMINISTIC")
    assert "DETERMINISTIC_SCENARIO" in deterministic
    assert "not a real-world 100%" in deterministic

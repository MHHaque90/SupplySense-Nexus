"""Baseline vs scenario comparison (Phase 8).

Comparison is scenario outcome MINUS baseline outcome — descriptive
scenario analysis, never optimization and never a recommendation.
"""

from backend.app.analytics.simulation.types import ScenarioOutcome


def compare(baseline: ScenarioOutcome, scenario: ScenarioOutcome) -> dict[str, float | None]:
    """Compute delta metrics between scenario and baseline outcomes."""
    def _delta(name: str) -> float | None:
        base = getattr(baseline, name)
        stressed = getattr(scenario, name)
        if base is None or stressed is None:
            return None
        return float(stressed - base)

    return {
        "delta_stockout_probability": _delta("stockout_probability"),
        "delta_unmet_demand": _delta("expected_unmet_demand"),
        "delta_min_inventory": _delta("expected_min_inventory"),
        "delta_ending_inventory": _delta("expected_ending_inventory"),
        "delta_stockout_days": _delta("expected_stockout_days"),
        "delta_service_exposure": _delta("service_exposure_probability"),
    }

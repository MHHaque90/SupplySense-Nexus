"""Decision comparison (Phase 9).

Reuses Phase 8 ``comparison.compare`` semantics: the second outcome
minus the first. Every delta is factual arithmetic. There is NO
ranking, scoring, tiering, or selection of any decision here — that is
explicitly Phase 10 scope.
"""

from backend.app.analytics.replay.types import ReplayResult
from backend.app.analytics.simulation import comparison as simulation_comparison
from backend.app.analytics.simulation.types import ScenarioOutcome


def compare_to_baseline(
    baseline: ScenarioOutcome,
    arms: list[tuple[str, str, ScenarioOutcome]],
) -> dict[str, dict[str, float | None]]:
    """Decision-arm outcome minus shared baseline outcome, per decision."""
    return {
        decision_id: simulation_comparison.compare(baseline, outcome)
        for _, decision_id, outcome in arms
    }


def pairwise(
    arms: list[tuple[str, str, ScenarioOutcome]],
) -> list[dict[str, object]]:
    """Factual decision-minus-decision deltas in declared order.

    Each entry reports ``deltas`` as RIGHT minus LEFT, matching the
    Phase 8 comparison convention. Entries are never sorted by metric,
    never scored, and never marked as better or worse.
    """
    comparisons: list[dict[str, object]] = []
    for index, (left_label, left_id, left_outcome) in enumerate(arms):
        for right_label, right_id, right_outcome in arms[index + 1:]:
            comparisons.append({
                "left_decision_id": left_id,
                "left_decision_type": left_label,
                "right_decision_id": right_id,
                "right_decision_type": right_label,
                "deltas": simulation_comparison.compare(left_outcome, right_outcome),
                "semantics": (
                    "deltas are right minus left; factual arithmetic only, "
                    "with no ranking or recommendation."
                ),
            })
    return comparisons


def result_deltas(results: list[ReplayResult]) -> dict[str, dict[str, float | None]]:
    """Return the recorded baseline deltas keyed by decision id."""
    return {result.decision_id: dict(result.baseline_delta) for result in results}

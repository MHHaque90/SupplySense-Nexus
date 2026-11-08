"""Fixed eight-intent taxonomy and the offline intent classifier (Phase 11).

The taxonomy is locked by ``docs/ai-assistant-design.md`` and must not grow:
``demand_forecast``, ``inventory_risk``, ``supplier_score``,
``scenario_creation``, ``decision_comparison``, ``assumption_explanation``,
``data_quality``, ``general_inquiry``.

:func:`classify` is deterministic and rule-based. It backs the offline
MockProvider so the chat flow stays fully functional with zero network
access; a cloud provider is prompted with the same taxonomy.
"""

from enum import StrEnum

DEFAULT_CONFIDENCE_WITH_TOOLS = 0.75
DEFAULT_CONFIDENCE_NO_TOOLS = 0.60


class Intent(StrEnum):
    """The eight supported request intents (no more may be added)."""

    DEMAND_FORECAST = "demand_forecast"
    INVENTORY_RISK = "inventory_risk"
    SUPPLIER_SCORE = "supplier_score"
    SCENARIO_CREATION = "scenario_creation"
    DECISION_COMPARISON = "decision_comparison"
    ASSUMPTION_EXPLANATION = "assumption_explanation"
    DATA_QUALITY = "data_quality"
    GENERAL_INQUIRY = "general_inquiry"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid intent values."""
        return [member.value for member in cls]


#: Keyword groups per intent; keywords are lowercase substrings. The
#: classifier scores all groups and picks the highest hit count (ties keep
#: this declaration order), so e.g. "simulate a supplier outage" resolves to
#: ``scenario_creation`` (two hits) instead of ``supplier_score`` (one hit).
_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (Intent.DEMAND_FORECAST.value, ("forecast", "demand", "predict", "next month")),
    (Intent.INVENTORY_RISK.value, ("stockout", "overstock", "inventory", "stock", "on-hand", "health", "at risk")),
    (Intent.SUPPLIER_SCORE.value, ("supplier", "delivery", "on-time", "scorecard", "vendor")),
    (Intent.SCENARIO_CREATION.value, ("simulate", "simulation", "scenario", "disruption", "outage", "delay", "what if")),
    (Intent.DECISION_COMPARISON.value, ("compare", "versus", " vs ", "expedite", "alternative", "reroute")),
    (Intent.DATA_QUALITY.value, ("quality", "missing data", "duplicate", "reconcil")),
    (Intent.ASSUMPTION_EXPLANATION.value, ("assumption", "confidence", "uncertainty", "caveat", "limitation")),
]

#: Default tool calls per intent (names must exist in the registry).
#: ``assumption_explanation`` and ``general_inquiry`` call no tools: they
#: answer from conversation context, never from new computation.
INTENT_DEFAULT_TOOLS: dict[str, tuple[str, ...]] = {
    Intent.DEMAND_FORECAST.value: ("get_forecast",),
    Intent.INVENTORY_RISK.value: ("get_inventory_health", "get_inventory_position"),
    Intent.SUPPLIER_SCORE.value: ("get_supplier_scorecard",),
    Intent.SCENARIO_CREATION.value: ("run_disruption_simulation",),
    Intent.DECISION_COMPARISON.value: ("run_decision_comparison",),
    Intent.ASSUMPTION_EXPLANATION.value: (),
    Intent.DATA_QUALITY.value: ("get_data_quality_report",),
    Intent.GENERAL_INQUIRY.value: (),
}


def classify(text: str) -> tuple[str, float]:
    """Classify one user message into ``(intent, heuristic_confidence)``.

    Rule-based and deterministic: every keyword group is scored by its
    number of hits; the highest score wins (ties keep declaration order);
    otherwise ``general_inquiry``. Confidence is a fixed offline heuristic
    (documented as such), not a calibrated statistical measure.
    """
    lowered = text.lower()
    best_intent: str | None = None
    best_score = 0
    for intent, keywords in _INTENT_KEYWORDS:
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > best_score:
            best_intent = intent
            best_score = score
    if best_intent is not None:
        return best_intent, DEFAULT_CONFIDENCE_WITH_TOOLS
    return Intent.GENERAL_INQUIRY.value, DEFAULT_CONFIDENCE_NO_TOOLS


_OPTIMIZATION_VOCABULARY = (
    "optimi",
    "minimi",
    "maximi",
    "budget",
    "order quantit",
    "allocation plan",
)


def select_tools(intent: str, text: str) -> tuple[str, ...]:
    """Select default tool calls for ``(intent, text)`` in offline mode.

    Starts from :data:`INTENT_DEFAULT_TOOLS` and adds
    ``run_optimization_analysis`` when the message uses optimization
    vocabulary, so the optimizer stays reachable without a cloud provider.
    The executor still enforces the per-turn tool-call cap.
    """
    lowered = text.lower()
    tools = list(INTENT_DEFAULT_TOOLS.get(intent, ()))
    if any(word in lowered for word in _OPTIMIZATION_VOCABULARY):
        tools.append("run_optimization_analysis")
    seen: set[str] = set()
    ordered: list[str] = []
    for name in tools:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


__all__ = [
    "DEFAULT_CONFIDENCE_NO_TOOLS",
    "DEFAULT_CONFIDENCE_WITH_TOOLS",
    "INTENT_DEFAULT_TOOLS",
    "Intent",
    "classify",
    "select_tools",
]

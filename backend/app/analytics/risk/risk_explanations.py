"""Explanation builders for aggregated risk (Phase 7).

Templated, evidence-backed sentences only. No causal claims, no
prescriptions, no simulation language.
"""

from backend.app.analytics.risk.types import RiskRecord

_SEVERITY_RANK = [
    "CRITICAL", "HIGH", "HIGH_EXPOSURE", "ELEVATED", "MODERATE", "MONITOR",
    "LOW", "NO_SIGNAL", "UNKNOWN",
]


def _rank(record: RiskRecord) -> int:
    try:
        return _SEVERITY_RANK.index(record.severity)
    except ValueError:
        return len(_SEVERITY_RANK)


def explain_overall(
    entity_id: str,
    severity: str,
    contributors: list[RiskRecord],
) -> str:
    """Explain an aggregated exposure from its contributors."""
    if not contributors:
        return f"Overall exposure for {entity_id} is {severity}: no contributing risks recorded."
    ordered = sorted(contributors, key=_rank)
    parts = "; ".join(
        f"{record.domain} is {record.severity} ({record.evidence[0]})"
        if record.evidence else f"{record.domain} is {record.severity}"
        for record in ordered[:3]
    )
    return (
        f"Overall exposure for {entity_id} is {severity}: {parts}. "
        "Descriptive combination only; no action is implied."
    )


def explain_combination(names: list[str], outcome: str) -> str:
    """Describe a documented evidence combination and its outcome."""
    return (
        f"Combined exposure pattern ({' + '.join(names)}) indicates {outcome}. "
        "This describes observed evidence, not a prediction of what happens next."
    )

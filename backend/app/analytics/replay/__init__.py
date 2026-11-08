"""Decision Replay Lab for SupplySense Nexus (Phase 9).

Replays explicitly defined business decisions under ONE frozen
disruption scenario with ONE shared baseline and common random
numbers. Produces factual decision-vs-baseline and decision-vs-decision
comparisons. Never ranks, recommends, optimizes, or selects decisions.

This analysis uses synthetic/simulated data. Scenario assumptions,
decision assumptions, and simulation outcomes are hypothetical and are
not evidence about real suppliers, real disruptions, or real business
operations.
"""

from backend.app.analytics.replay import (
    comparison,
    constraints,
    costs,
    decisions,
    effects,
    replay,
    reports,
    traceability,
    types,
    validation,
)
from backend.app.analytics.replay.types import (
    DECISION_TYPES,
    DEFAULT_REPLAY_CONFIG,
    Decision,
    ReplayConfig,
    ReplayResult,
)

__all__ = [
    "DECISION_TYPES",
    "DEFAULT_REPLAY_CONFIG",
    "Decision",
    "ReplayConfig",
    "ReplayResult",
    "comparison",
    "constraints",
    "costs",
    "decisions",
    "effects",
    "reports",
    "replay",
    "traceability",
    "types",
    "validation",
]

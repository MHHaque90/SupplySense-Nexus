"""Typed Decision Replay contracts (Phase 9)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReplayConfig:
    """Explicit replay configuration. Every setting documented.

    - max_decisions: upper bound guarding runaway replay batches.
    - default_horizon_days: fallback horizon when the scenario omits one.
    - require_validation: when True, invalid decisions abort the replay
      instead of being skipped with a recorded note.
    """

    max_decisions: int = 16
    default_horizon_days: int = 28
    require_validation: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "max_decisions": self.max_decisions,
            "default_horizon_days": self.default_horizon_days,
            "require_validation": self.require_validation,
        }


DEFAULT_REPLAY_CONFIG = ReplayConfig()

DECISION_TYPES = (
    "NO_ACTION",
    "EXPEDITE_INBOUND",
    "ALTERNATIVE_SUPPLIER",
    "SUPPLIER_ALLOCATION_CHANGE",
    "INVENTORY_TRANSFER",
    "DEMAND_ADJUSTMENT",
    "PURCHASE_ORDER_ADJUSTMENT",
    "COMBINED_ACTION",
)


@dataclass
class Decision:
    """An explicitly defined business decision (assumptions, not facts)."""

    decision_id: str
    decision_type: str
    description: str = ""
    affected_suppliers: list[str] = field(default_factory=list)
    affected_products: list[str] = field(default_factory=list)
    affected_warehouses: list[str] = field(default_factory=list)
    quantities: dict[str, float] = field(default_factory=dict)
    timing: dict[str, int] = field(default_factory=dict)
    cost_assumptions: dict[str, float] = field(default_factory=dict)
    constraints_checked: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source: str = "user_defined"
    components: list["Decision"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the decision."""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "description": self.description,
            "affected_suppliers": self.affected_suppliers,
            "affected_products": self.affected_products,
            "affected_warehouses": self.affected_warehouses,
            "quantities": self.quantities,
            "timing": self.timing,
            "cost_assumptions": self.cost_assumptions,
            "constraints_checked": self.constraints_checked,
            "assumptions": self.assumptions,
            "source": self.source,
            "components": [item.to_dict() for item in self.components],
        }


@dataclass
class ReplayResult:
    """One decision arm replayed under the shared scenario.

    - outcome: serialized ScenarioOutcome for this arm.
    - baseline_delta: factual deltas of this arm minus the shared baseline.
    - decision_cost: decision/disruption/total modeled costs (None when unknown).
    - validation: notes produced while validating the decision.
    - constraint_notes: descriptive PASS/UNCHECKED/FAIL checks (never FAIL here).
    - effect_notes: copy-on-write transform notes for this arm.
    - sample_fingerprint: digest of the shared sampled parameter arrays; every
      arm replayed in one run carries the same fingerprint (common random
      numbers). Not a score of any kind — it identifies sample provenance only.
    - traceability: per-entity provenance chains with decision fields.
    """

    replay_id: str
    scenario_id: str
    decision_id: str
    decision_type: str
    outcome: dict[str, Any] = field(default_factory=dict)
    baseline_delta: dict[str, float | None] = field(default_factory=dict)
    decision_cost: dict[str, float | None] = field(default_factory=dict)
    validation: list[str] = field(default_factory=list)
    traceability: dict[str, Any] = field(default_factory=dict)
    synthetic: bool = True
    constraint_notes: list[str] = field(default_factory=list)
    effect_notes: list[str] = field(default_factory=list)
    sample_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the replay result."""
        return {
            "replay_id": self.replay_id,
            "scenario_id": self.scenario_id,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "outcome": self.outcome,
            "baseline_delta": self.baseline_delta,
            "decision_cost": self.decision_cost,
            "validation": self.validation,
            "constraint_notes": self.constraint_notes,
            "effect_notes": self.effect_notes,
            "sample_fingerprint": self.sample_fingerprint,
            "traceability": self.traceability,
            "synthetic": self.synthetic,
        }

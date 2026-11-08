"""Decision construction for the Replay Lab (Phase 9).

Builders validate structural shape (known type, deterministic ID) and
attach assumption notes. Semantic validation against data lives in
validation.py; constraint checks live in constraints.py. No decision
is ever selected, ranked, or recommended here.
"""

import hashlib

from backend.app.analytics.replay.types import DECISION_TYPES, Decision

_ASSUMPTION_NOTE = "This value is a decision assumption and is not an observed historical fact."


def deterministic_id(replay_id: str, decision_type: str, target: str) -> str:
    """Build a deterministic decision ID from replay, type, and target."""
    digest = hashlib.sha256(f"{replay_id}:{decision_type}:{target}".encode()).hexdigest()
    return f"{replay_id}-{decision_type.lower()}-{digest[:8]}"


def build_decision(
    replay_id: str,
    decision_type: str,
    description: str = "",
    affected_suppliers: list[str] | None = None,
    affected_products: list[str] | None = None,
    affected_warehouses: list[str] | None = None,
    quantities: dict[str, float] | None = None,
    timing: dict[str, int] | None = None,
    cost_assumptions: dict[str, float] | None = None,
    assumptions: list[str] | None = None,
    components: list[Decision] | None = None,
    source: str = "user_defined",
) -> Decision:
    """Construct a typed Decision with deterministic identity."""
    if decision_type not in DECISION_TYPES:
        raise ValueError(
            f"Unknown decision type: {decision_type}. Valid: {sorted(DECISION_TYPES)}."
        )
    suppliers = list(affected_suppliers or [])
    products = list(affected_products or [])
    warehouses = list(affected_warehouses or [])
    target = "|".join(sorted(suppliers + products + warehouses)) or "global"
    notes = [f"decision_type = {decision_type}. {_ASSUMPTION_NOTE}"]
    notes.extend(f"{note} (decision assumption)." for note in (assumptions or []))
    if decision_type == "COMBINED_ACTION":
        if not components:
            raise ValueError("COMBINED_ACTION requires at least one component decision.")
        for component in components:
            if component.decision_type == "COMBINED_ACTION":
                raise ValueError(
                    "COMBINED_ACTION cannot nest inside another COMBINED_ACTION."
                )
            notes.append(
                f"Component {component.decision_id} ({component.decision_type}) "
                f"applied in declared order. {_ASSUMPTION_NOTE}"
            )
    return Decision(
        decision_id=deterministic_id(replay_id, decision_type, target),
        decision_type=decision_type,
        description=description,
        affected_suppliers=suppliers,
        affected_products=products,
        affected_warehouses=warehouses,
        quantities=dict(quantities or {}),
        timing=dict(timing or {}),
        cost_assumptions=dict(cost_assumptions or {}),
        assumptions=notes,
        source=source,
        components=list(components or []),
    )


def build_no_action(replay_id: str) -> Decision:
    """Build the NO_ACTION control arm (identity transformation)."""
    return build_decision(
        replay_id, "NO_ACTION",
        description="No business action taken; disrupted scenario runs unmodified.",
        assumptions=["No changes to demand, inbound, inventory, or supplier attribution."],
    )


def decision_from_dict(replay_id: str, payload: dict) -> Decision:
    """Parse a user-supplied JSON-style decision definition."""
    if not isinstance(payload, dict):
        raise ValueError("Decision definition must be a JSON object.")
    decision_type = payload.get("decision_type", "")
    components = [
        decision_from_dict(replay_id, item) for item in payload.get("components", [])
    ]
    timing = {key: int(value) for key, value in dict(payload.get("timing", {})).items()}
    quantities = {key: float(value) for key, value in dict(payload.get("quantities", {})).items()}
    costs = {key: float(value) for key, value in dict(payload.get("cost_assumptions", {})).items()}
    return build_decision(
        replay_id,
        decision_type,
        description=str(payload.get("description", "")),
        affected_suppliers=list(payload.get("affected_suppliers", []) or []),
        affected_products=list(payload.get("affected_products", []) or []),
        affected_warehouses=list(payload.get("affected_warehouses", []) or []),
        quantities=quantities,
        timing=timing,
        cost_assumptions=costs,
        assumptions=list(payload.get("assumptions", []) or []),
        components=components,
        source=str(payload.get("source", "user_defined")),
    )

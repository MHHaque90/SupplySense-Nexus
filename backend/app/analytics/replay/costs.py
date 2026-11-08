"""Decision cost assembly (Phase 9).

Only two cost kinds exist: observed purchase cost (quantity ×
SupplierProduct.unit_cost) and explicit USER_ASSUMED_COST values
supplied with the decision. Missing costs are None with an explanatory
note — never zero, never fabricated. No best/minimum/optimal cost is
ever computed.
"""

from typing import Any

import pandas as pd

from backend.app.analytics.replay.types import Decision


def purchase_unit_cost(
    supplier_id: str,
    product_id: str,
    supplier_links: pd.DataFrame,
) -> float | None:
    """Return observed unit cost for a supplier-product link, if present."""
    if supplier_links.empty:
        return None
    own = supplier_links[
        (supplier_links["supplier_id"].astype(str) == supplier_id)
        & (supplier_links["product_id"].astype(str) == product_id)
    ]
    if own.empty or "unit_cost" not in own.columns:
        return None
    value = pd.to_numeric(own["unit_cost"], errors="coerce").dropna()
    if value.empty:
        return None
    return float(value.iloc[0])


def modeled_quantities(decision: Decision) -> dict[str, float]:
    """Return the explicit modeled quantities a decision puts into motion.

    Keys are quantity names; allocation decisions key by supplier so the
    observed purchase cost stays attributable per supplier-product link.
    """
    quantities = {
        name: float(value) for name, value in decision.quantities.items()
        if name not in ("demand_multiplier", "multiplier")
    }
    if decision.decision_type == "COMBINED_ACTION":
        merged: dict[str, float] = {}
        for component in decision.components:
            for name, value in modeled_quantities(component).items():
                key = name if name not in merged else f"{name}@{component.decision_id}"
                merged[key] = value
        return merged
    return quantities


def compute_costs(
    decision: Decision,
    modeled_quantities: dict[str, float],
    supplier_links: pd.DataFrame,
    disruption_cost_per_unmet_unit: float | None = None,
    unmet_demand: float | None = None,
) -> dict[str, Any]:
    """Assemble decision/disruption/total modeled costs with provenance."""
    notes: dict[str, str] = {}
    decision_cost: float | None = None
    assumed_total = 0.0
    assumed_found = False
    rate = disruption_cost_per_unmet_unit
    for name, value in decision.cost_assumptions.items():
        if value < 0:
            raise ValueError(f"Cost assumption '{name}' must be non-negative.")
        if name == "disruption_cost_per_unmet_unit":
            # Modelling rate, not a decision spend; never double counted.
            rate = float(value) if rate is None else rate
            continue
        assumed_total += float(value)
        assumed_found = True
        notes[name] = "USER_ASSUMED_COST"
    supplier_set = set(decision.affected_suppliers)
    observed_total = 0.0
    observed_found = False
    for name, quantity in modeled_quantities.items():
        supplier_scope = (
            [name] if name in supplier_set else list(decision.affected_suppliers or [None])
        )
        for supplier_id in supplier_scope:
            for product_id in decision.affected_products or [None]:
                unit = purchase_unit_cost(str(supplier_id), str(product_id), supplier_links)
                if unit is not None:
                    observed_total += float(quantity) * unit
                    observed_found = True
                    notes[f"{name}@observed"] = "OBSERVED_PURCHASE_COST"
    parts: list[float] = []
    if assumed_found:
        parts.append(assumed_total)
        decision_cost = assumed_total
    if observed_found:
        parts.append(observed_total)
        decision_cost = (decision_cost or 0.0) + observed_total
    disruption_cost: float | None = None
    if rate is not None and unmet_demand is not None:
        if rate < 0:
            raise ValueError("disruption_cost_per_unmet_unit must be non-negative.")
        disruption_cost = float(rate) * float(unmet_demand)
        notes["disruption"] = "USER_ASSUMED_COST"
    total = None
    if decision_cost is not None or disruption_cost is not None:
        total = (decision_cost or 0.0) + (disruption_cost or 0.0)
    if decision_cost is None and disruption_cost is None:
        notes["total"] = "No cost assumptions or observed costs available."
    return {
        "decision_cost": decision_cost,
        "disruption_cost": disruption_cost,
        "total_modeled_cost": total,
        "cost_notes": notes,
    }

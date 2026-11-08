"""Decision validation against observed data (Phase 9).

Every rejection raises ValueError with an explicit message. Validation
runs BEFORE simulation so no compute is wasted on invalid decisions.
"""

import pandas as pd

from backend.app.analytics.replay.types import DECISION_TYPES, Decision

# Explicitly required decision parameters, checked after identity,
# quantity, and timing checks so messages stay specific.
_REQUIRED_QUANTITIES = {
    "EXPEDITE_INBOUND": ("expedite_units",),
    "DEMAND_ADJUSTMENT": ("demand_multiplier", "multiplier"),
    "PURCHASE_ORDER_ADJUSTMENT": ("order_units", "quantity"),
    "INVENTORY_TRANSFER": ("transfer_units",),
}
# Explicitly required decision parameters, checked after identity,
# quantity, and timing checks so messages stay specific. Timing groups
# list ALTERNATIVES: any one key in the group satisfies the requirement
# (PURCHASE_ORDER_ADJUSTMENT accepts arrival_day or start_day).
_REQUIRED_TIMING = {
    "EXPEDITE_INBOUND": (("delay_reduction_days",),),
    "PURCHASE_ORDER_ADJUSTMENT": (("arrival_day", "start_day"),),
}


def _known_ids(frame: pd.DataFrame, column: str) -> set[str]:
    if frame.empty or column not in frame.columns:
        return set()
    return {str(value) for value in frame[column].tolist()}


def _require_parameters(decision: Decision, horizon_days: int) -> list[str]:
    """Reject decisions missing parameters their transform depends on."""
    notes: list[str] = []
    quantity_keys = _REQUIRED_QUANTITIES.get(decision.decision_type, ())
    if quantity_keys and not any(key in decision.quantities for key in quantity_keys):
        raise ValueError(
            f"Missing required decision parameter: quantities.{quantity_keys[0]} "
            f"for {decision.decision_type}."
        )
    timing_groups = _REQUIRED_TIMING.get(decision.decision_type, ())
    for group in timing_groups:
        if not any(key in decision.timing for key in group):
            expected = " or ".join(f"timing.{key}" for key in group)
            raise ValueError(
                f"Missing required decision parameter: {expected} "
                f"for {decision.decision_type}."
            )
    if decision.decision_type == "EXPEDITE_INBOUND":
        reduction = int(decision.timing["delay_reduction_days"])
        if reduction <= 0:
            raise ValueError(
                f"timing.delay_reduction_days must be > 0, got {reduction}."
            )
        notes.append(f"PASS: delay_reduction_days = {reduction} (decision assumption).")
    if decision.decision_type == "PURCHASE_ORDER_ADJUSTMENT":
        arrival = int(
            decision.timing.get("arrival_day", decision.timing.get("start_day", 0))
        )
        if not 0 <= arrival < horizon_days:
            raise ValueError(
                f"arrival_day {arrival} outside [0, {horizon_days})."
            )
        notes.append(f"PASS: arrival_day {arrival} within horizon.")
    if decision.decision_type == "ALTERNATIVE_SUPPLIER":
        if not decision.affected_suppliers:
            raise ValueError("ALTERNATIVE_SUPPLIER requires an explicit affected_suppliers entry.")
        if not decision.affected_products:
            raise ValueError("ALTERNATIVE_SUPPLIER requires an explicit affected_products entry.")
        if not decision.quantities:
            raise ValueError("ALTERNATIVE_SUPPLIER requires an explicit quantity.")
        notes.append(
            f"PASS: alternative supplier {decision.affected_suppliers[0]} is an "
            "explicit user selection (not selected or ranked by this system)."
        )
    if decision.decision_type == "INVENTORY_TRANSFER" and len(
        decision.affected_products
    ) != 1:
        raise ValueError("INVENTORY_TRANSFER requires exactly one product.")
    return notes


def _require_allocations(
    decision: Decision, supplier_ids: set[str], product_ids: set[str],
    supplier_products: set[tuple[str, str]],
) -> list[str]:
    """Reject incomplete or invalid explicit supplier allocations."""
    notes: list[str] = []
    allocations = decision.quantities
    total = 0.0
    for supplier_id, value in allocations.items():
        if supplier_id not in supplier_ids:
            raise ValueError(f"Unknown supplier: {supplier_id}.")
        total += float(value)
        notes.append(f"PASS: allocation for {supplier_id} = {value} (decision assumption).")
    if total <= 0:
        raise ValueError("Allocation quantities must sum to a positive total.")
    for supplier_id in decision.affected_suppliers:
        if supplier_id not in allocations:
            raise ValueError(
                f"Missing allocation quantity for affected supplier {supplier_id}."
            )
    for product_id in decision.affected_products:
        if product_id not in product_ids:
            raise ValueError(f"Unknown product: {product_id}.")
        for supplier_id in decision.affected_suppliers:
            if (supplier_id, product_id) not in supplier_products:
                raise ValueError(
                    f"Supplier {supplier_id} does not supply product {product_id}."
                )
            notes.append(
                f"PASS: supplier-product relationship {supplier_id}|{product_id} exists."
            )
    return notes


def validate_decision(
    decision: Decision,
    horizon_days: int,
    supplier_ids: set[str],
    product_ids: set[str],
    warehouse_ids: set[str],
    supplier_products: set[tuple[str, str]],
    series_keys: set[tuple[str, str]],
    on_hand: dict[tuple[str, str], float],
) -> list[str]:
    """Validate one decision, returning check notes or raising ValueError."""
    notes: list[str] = []
    if decision.decision_type not in DECISION_TYPES:
        raise ValueError(
            f"Unknown decision type: {decision.decision_type}. "
            f"Valid: {sorted(DECISION_TYPES)}."
        )
    if decision.decision_type == "COMBINED_ACTION":
        if not decision.components:
            raise ValueError("COMBINED_ACTION requires at least one component decision.")
        for component in decision.components:
            notes.extend(validate_decision(
                component, horizon_days, supplier_ids, product_ids,
                warehouse_ids, supplier_products, series_keys, on_hand,
            ))
            notes.append(
                f"Component {component.decision_id} validated in declared order."
            )
        return notes
    for supplier_id in decision.affected_suppliers:
        if supplier_id not in supplier_ids:
            raise ValueError(f"Unknown supplier: {supplier_id}.")
        notes.append(f"PASS: supplier {supplier_id} exists.")
    for product_id in decision.affected_products:
        if product_id not in product_ids:
            raise ValueError(f"Unknown product: {product_id}.")
        notes.append(f"PASS: product {product_id} exists.")
    for warehouse_id in decision.affected_warehouses:
        if warehouse_id not in warehouse_ids:
            raise ValueError(f"Unknown warehouse: {warehouse_id}.")
        notes.append(f"PASS: warehouse {warehouse_id} exists.")
    for name, value in decision.quantities.items():
        if value <= 0:
            raise ValueError(f"Quantity '{name}' must be > 0, got {value}.")
        notes.append(f"PASS: quantity '{name}' is positive.")
    if decision.decision_type == "SUPPLIER_ALLOCATION_CHANGE" and not decision.quantities:
        raise ValueError("SUPPLIER_ALLOCATION_CHANGE requires explicit allocation quantities.")
    start = decision.timing.get("start_day", 0)
    end = decision.timing.get("end_day", horizon_days)
    if not 0 <= start < horizon_days:
        raise ValueError(f"start_day {start} outside [0, {horizon_days}).")
    if not 0 < end <= horizon_days or end <= start:
        raise ValueError(f"end_day {end} must satisfy start_day < end_day <= {horizon_days}.")
    notes.append("PASS: timing within horizon.")
    notes.extend(_require_parameters(decision, horizon_days))
    if decision.decision_type == "SUPPLIER_ALLOCATION_CHANGE":
        notes.extend(_require_allocations(
            decision, supplier_ids, product_ids, supplier_products
        ))
        return notes
    if decision.decision_type in (
        "ALTERNATIVE_SUPPLIER", "PURCHASE_ORDER_ADJUSTMENT",
    ):
        for supplier_id in decision.affected_suppliers:
            for product_id in decision.affected_products:
                if (supplier_id, product_id) not in supplier_products:
                    raise ValueError(
                        f"Supplier {supplier_id} does not supply product {product_id}."
                    )
                notes.append(
                    f"PASS: supplier-product relationship {supplier_id}|{product_id} exists."
                )
    if decision.decision_type == "INVENTORY_TRANSFER":
        if len(decision.affected_warehouses) != 2:
            raise ValueError("INVENTORY_TRANSFER requires exactly two warehouses.")
        source = (decision.affected_products[0], decision.affected_warehouses[0]) \
            if decision.affected_products else None
        quantity = decision.quantities.get("transfer_units", 0.0)
        if source and quantity > on_hand.get(source, 0.0):
            raise ValueError(
                f"Insufficient source inventory: {quantity} requested, "
                f"{on_hand.get(source, 0.0)} available."
            )
        notes.append("PASS: source inventory sufficient.")
    return notes


def validate_scenario_membership(
    decision: Decision,
    scenario_series: set[tuple[str, str]],
) -> None:
    """Reject decisions targeting entities outside the scenario scope."""
    targets: set[tuple[str, str]] = set()

    def _collect(item: Decision) -> None:
        for product_id in item.affected_products:
            if item.affected_warehouses:
                for warehouse_id in item.affected_warehouses:
                    targets.add((product_id, warehouse_id))
            else:
                matched = {key for key in scenario_series if key[0] == product_id}
                if not matched:
                    raise ValueError(
                        f"Decision targets outside scenario scope: no scenario "
                        f"series for product {product_id}."
                    )
                targets.update(matched)

    _collect(decision)
    for component in decision.components:
        _collect(component)
    unknown = targets - scenario_series
    if unknown:
        raise ValueError(
            f"Decision targets outside scenario scope: {sorted(unknown)}."
        )

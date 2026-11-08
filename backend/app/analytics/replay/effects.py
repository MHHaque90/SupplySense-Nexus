"""Copy-on-write decision effects (Phase 9).

Every transform receives copies of simulation inputs and returns
transformed copies plus assumption notes. Nothing here mutates the
baseline, the scenario, loader frames, or database records.

State model per entity (all plain data):
- demand: list[float] over the horizon
- schedule: list of inbound dicts {day_offset, quantity, supplier_id, po_id, ...}
- on_hand: float (paired transfer entries only; conservation-checked)
"""

import copy

from backend.app.analytics.replay.types import Decision


def _window(decision: Decision, horizon: int) -> tuple[int, int]:
    start = int(decision.timing.get("start_day", 0))
    end = int(decision.timing.get("end_day", horizon))
    return max(0, start), min(end, horizon)


def apply_no_action(demand, schedule, on_hand, horizon):
    """Identity transformation (control arm)."""
    return {
        "demand": list(demand),
        "schedule": copy.deepcopy(schedule),
        "on_hand": on_hand,
        "notes": ["NO_ACTION: no changes to demand, inbound, or inventory (decision assumption)."],
    }


def shift_arrival_earlier(schedule, quantity, reduction_days, start, end, horizon):
    """Move selected inbound earlier without negative-delay semantics."""
    if quantity <= 0:
        raise ValueError("expedite quantity must be > 0.")
    if reduction_days <= 0:
        raise ValueError("delay_reduction_days must be > 0.")
    moved = copy.deepcopy(schedule)
    remaining = float(quantity)
    notes = []
    for entry in sorted(moved, key=lambda item: int(item.get("day_offset", -1))):
        if remaining <= 0:
            break
        offset = int(entry.get("day_offset", -1))
        if not 0 <= offset < horizon:
            continue
        if not start <= offset < end:
            continue
        available = float(entry.get("quantity", 0.0))
        if available <= 0:
            continue
        take = min(available, remaining)
        entry["quantity"] = available - take
        new_offset = max(0, offset - reduction_days)
        moved.append({
            "date": entry.get("date", ""),
            "day_offset": new_offset,
            "quantity": take,
            "supplier_id": entry.get("supplier_id"),
            "po_id": entry.get("po_id"),
            "affected_by_event": entry.get("affected_by_event", False),
            "event_id": entry.get("event_id"),
            "expedited": True,
        })
        remaining -= take
        notes.append(
            f"Moved {take} units from day {offset} to day {new_offset} "
            f"(decision assumption)."
        )
    if remaining > 0:
        notes.append(
            f"Only {quantity - remaining} of {quantity} requested units were "
            f"available to expedite (decision assumption)."
        )
    return moved, notes


def apply_expedite_inbound(demand, schedule, on_hand, decision, horizon):
    """EXPEDITE_INBOUND: shift selected inbound earlier on copies."""
    quantity = float(decision.quantities.get("expedite_units", 0.0))
    reduction = int(decision.timing.get("delay_reduction_days", 0))
    start, end = _window(decision, horizon)
    moved, notes = shift_arrival_earlier(schedule, quantity, reduction, start, end, horizon)
    notes.insert(0, "EXPEDITE_INBOUND applied to copied inbound schedule (decision assumption).")
    return {"demand": list(demand), "schedule": moved, "on_hand": on_hand, "notes": notes}


def apply_alternative_supplier(demand, schedule, on_hand, decision, horizon):
    """ALTERNATIVE_SUPPLIER: rewrite arrival attribution on copies."""
    suppliers = list(decision.affected_suppliers)
    if not suppliers:
        raise ValueError("ALTERNATIVE_SUPPLIER requires an explicit affected_suppliers entry.")
    moved = copy.deepcopy(schedule)
    reassigned = 0
    for entry in moved:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon:
            entry["supplier_id"] = suppliers[0]
            reassigned += 1
    notes = [
        f"ALTERNATIVE_SUPPLIER: {reassigned} arrival(s) re-attributed to "
        f"{suppliers[0]} on copied inputs (decision assumption).",
    ]
    return {"demand": list(demand), "schedule": moved, "on_hand": on_hand, "notes": notes}


def apply_supplier_allocation(demand, schedule, on_hand, decision, horizon):
    """SUPPLIER_ALLOCATION_CHANGE: split quantities across suppliers."""
    allocations = decision.quantities
    if not allocations:
        raise ValueError("SUPPLIER_ALLOCATION_CHANGE requires explicit allocation quantities.")
    total = sum(float(value) for value in allocations.values())
    if total <= 0:
        raise ValueError("Allocation quantities must sum to a positive total.")
    moved = copy.deepcopy(schedule)
    # Snapshot the original entries so the split entries appended below are
    # never re-split by this loop (each inbound is split exactly once).
    for entry in list(moved):
        offset = int(entry.get("day_offset", -1))
        if not 0 <= offset < horizon:
            continue
        quantity = float(entry.get("quantity", 0.0))
        if quantity <= 0:
            continue
        entry["quantity"] = 0.0
        for supplier, share in sorted(allocations.items()):
            moved.append({
                "date": entry.get("date", ""),
                "day_offset": offset,
                "quantity": quantity * float(share) / total,
                "supplier_id": supplier,
                "po_id": entry.get("po_id"),
                "affected_by_event": entry.get("affected_by_event", False),
                "event_id": entry.get("event_id"),
                "allocated": True,
            })
    notes = [
        f"SUPPLIER_ALLOCATION_CHANGE split inbound across "
        f"{sorted(allocations)} proportionally to stated amounts "
        f"(total {total}, decision assumption).",
    ]
    return {"demand": list(demand), "schedule": moved, "on_hand": on_hand, "notes": notes}


def apply_inventory_transfer(demand_by_key, on_hand_by_key, decision):
    """INVENTORY_TRANSFER: paired decrease/increase with conservation."""
    if len(decision.affected_warehouses) != 2:
        raise ValueError("INVENTORY_TRANSFER requires exactly two warehouses.")
    if len(decision.affected_products) != 1:
        raise ValueError("INVENTORY_TRANSFER requires exactly one product.")
    quantity = float(decision.quantities.get("transfer_units", 0.0))
    if quantity <= 0:
        raise ValueError("transfer_units must be > 0.")
    product = decision.affected_products[0]
    source_key = (product, decision.affected_warehouses[0])
    destination_key = (product, decision.affected_warehouses[1])
    if source_key == destination_key:
        raise ValueError("Source and destination must differ.")
    updated = dict(on_hand_by_key)
    updated[source_key] = updated.get(source_key, 0.0) - quantity
    updated[destination_key] = updated.get(destination_key, 0.0) + quantity
    notes = [
        f"INVENTORY_TRANSFER moved {quantity} units of {product} from "
        f"{source_key[1]} to {destination_key[1]} on copied balances "
        f"(decision assumption). Conservation holds by construction.",
    ]
    return {"demand_by_key": dict(demand_by_key), "on_hand_by_key": updated, "notes": notes}


def apply_demand_adjustment(demand, schedule, on_hand, decision, horizon):
    """DEMAND_ADJUSTMENT: scale demand over the timing window."""
    from backend.app.analytics.simulation import demand_effects

    multiplier = float(decision.quantities.get("demand_multiplier",
                                               decision.quantities.get("multiplier", 1.0)))
    if multiplier <= 0:
        raise ValueError("demand_multiplier must be positive.")
    start, end = _window(decision, horizon)
    adjusted, _, _ = demand_effects.apply_demand_multiplier(
        list(demand), list(demand), list(demand), multiplier, start, end
    )
    notes = [
        f"DEMAND_ADJUSTMENT scaled demand by {multiplier} over days "
        f"[{start}, {end}) (decision assumption, not a forecast).",
    ]
    return {"demand": adjusted, "schedule": copy.deepcopy(schedule),
            "on_hand": on_hand, "notes": notes}


def apply_purchase_order_adjustment(demand, schedule, on_hand, decision, horizon):
    """PURCHASE_ORDER_ADJUSTMENT: add explicit modeled inbound entries."""
    quantity = float(decision.quantities.get("order_units",
                                             decision.quantities.get("quantity", 0.0)))
    if quantity <= 0:
        raise ValueError("PURCHASE_ORDER_ADJUSTMENT requires a positive order quantity.")
    arrival_day = int(decision.timing.get("arrival_day", decision.timing.get("start_day", 0)))
    if not 0 <= arrival_day < horizon:
        raise ValueError(f"arrival_day {arrival_day} outside [0, {horizon}).")
    moved = copy.deepcopy(schedule)
    moved.append({
        "date": "",
        "day_offset": arrival_day,
        "quantity": quantity,
        "supplier_id": (decision.affected_suppliers or [None])[0],
        "po_id": "MODELED-PO",
        "affected_by_event": False,
        "event_id": None,
        "modeled": True,
    })
    notes = [
        f"PURCHASE_ORDER_ADJUSTMENT added modeled inbound of {quantity} units "
        f"on day {arrival_day} (decision assumption; PostgreSQL untouched).",
    ]
    return {"demand": list(demand), "schedule": moved, "on_hand": on_hand, "notes": notes}


def apply_decision(demand, schedule, on_hand, decision, horizon):
    """Dispatch one decision to its transform (COMBINED applies in order)."""
    if decision.decision_type == "NO_ACTION":
        return apply_no_action(demand, schedule, on_hand, horizon)
    if decision.decision_type == "EXPEDITE_INBOUND":
        return apply_expedite_inbound(demand, schedule, on_hand, decision, horizon)
    if decision.decision_type == "ALTERNATIVE_SUPPLIER":
        return apply_alternative_supplier(demand, schedule, on_hand, decision, horizon)
    if decision.decision_type == "SUPPLIER_ALLOCATION_CHANGE":
        return apply_supplier_allocation(demand, schedule, on_hand, decision, horizon)
    if decision.decision_type == "DEMAND_ADJUSTMENT":
        return apply_demand_adjustment(demand, schedule, on_hand, decision, horizon)
    if decision.decision_type == "PURCHASE_ORDER_ADJUSTMENT":
        return apply_purchase_order_adjustment(demand, schedule, on_hand, decision, horizon)
    if decision.decision_type == "INVENTORY_TRANSFER":
        raise ValueError("INVENTORY_TRANSFER applies across series; use apply_transfer_pair.")
    if decision.decision_type == "COMBINED_ACTION":
        state = {"demand": list(demand), "schedule": copy.deepcopy(schedule),
                 "on_hand": on_hand, "notes": []}
        for component in decision.components:
            if component.decision_type == "INVENTORY_TRANSFER":
                raise ValueError("INVENTORY_TRANSFER cannot nest inside COMBINED_ACTION.")
            piece = apply_decision(state["demand"], state["schedule"],
                                   state["on_hand"], component, horizon)
            state = {"demand": piece["demand"], "schedule": piece["schedule"],
                     "on_hand": piece["on_hand"],
                     "notes": state["notes"] + [f"[{component.decision_type}]"] + piece["notes"]}
        state["notes"].insert(
            0, "COMBINED_ACTION applied components in declared order (decision assumption).")
        return state
    raise ValueError(f"Unknown decision type: {decision.decision_type}.")


def apply_transfer_pair(demand_by_key, on_hand_by_key, decision):
    """Apply INVENTORY_TRANSFER across a series pair (top-level entry)."""
    if decision.decision_type != "INVENTORY_TRANSFER":
        raise ValueError("apply_transfer_pair requires an INVENTORY_TRANSFER decision.")
    return apply_inventory_transfer(demand_by_key, on_hand_by_key, decision)

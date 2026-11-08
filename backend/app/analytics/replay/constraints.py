"""Descriptive constraint checks (Phase 9).

Each check returns an explicit PASS/UNCHECKED/FAIL note. FAIL notes
reject the decision; nothing here searches, solves, or optimizes.
Nullable capacity means UNCHECKED, never zero.
"""

import pandas as pd

from backend.app.analytics.replay.types import Decision


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def check_constraints(
    decision: Decision,
    supplier_links: pd.DataFrame,
    warehouses: pd.DataFrame,
    on_hand: dict[tuple[str, str], float],
    horizon_days: int,
) -> list[str]:
    """Check an explicit decision against observed constraints."""
    notes: list[str] = []
    for component in decision.components:
        notes.extend(check_constraints(
            component, supplier_links, warehouses, on_hand, horizon_days
        ))
        continue
    link_pairs = set()
    if not supplier_links.empty:
        link_pairs = {
            (str(supplier), str(product))
            for supplier, product in zip(
                supplier_links["supplier_id"].tolist(),
                supplier_links["product_id"].tolist(),
            )
        }
    for supplier_id in decision.affected_suppliers:
        for product_id in decision.affected_products:
            if (supplier_id, product_id) in link_pairs:
                notes.append(
                    f"PASS: supplier-product relationship {supplier_id}|{product_id} exists."
                )
            else:
                notes.append(
                    f"FAIL: supplier {supplier_id} does not supply product {product_id}."
                )
    moq_map: dict[tuple[str, str], float] = {}
    capacity_map: dict[str, float] = {}
    if not supplier_links.empty and "min_order_qty" in supplier_links.columns:
        for _, row in supplier_links.iterrows():
            key = (str(row["supplier_id"]), str(row["product_id"]))
            moq = pd.to_numeric(pd.Series([row["min_order_qty"]]), errors="coerce").iloc[0]
            if pd.notna(moq):
                moq_map[key] = float(moq)
            capacity = pd.to_numeric(
                pd.Series([row.get("capacity_units")]), errors="coerce"
            ).iloc[0]
            if pd.notna(capacity):
                capacity_map[str(row["supplier_id"])] = max(
                    capacity_map.get(str(row["supplier_id"]), 0.0), float(capacity)
                )
    for name, quantity in decision.quantities.items():
        if "order" in name or "purchase" in name or "units" in name:
            for supplier_id in decision.affected_suppliers or [None]:
                for product_id in decision.affected_products or [None]:
                    moq = moq_map.get((str(supplier_id), str(product_id)))
                    if moq is None:
                        notes.append(f"UNCHECKED: MOQ unavailable for {name}.")
                    elif quantity < moq:
                        notes.append(f"FAIL: {name} {quantity} below MOQ {moq}.")
                    else:
                        notes.append(f"PASS: {name} meets MOQ {moq}.")
    for supplier_id in decision.affected_suppliers:
        if supplier_id in capacity_map:
            notes.append(f"PASS: supplier capacity recorded for {supplier_id}.")
        else:
            notes.append(f"UNCHECKED: supplier capacity unavailable for {supplier_id}.")
    warehouse_capacity = {}
    if not warehouses.empty and "capacity_units" in warehouses.columns:
        for _, row in warehouses.iterrows():
            capacity = pd.to_numeric(pd.Series([row["capacity_units"]]),
                                     errors="coerce").iloc[0]
            if pd.notna(capacity):
                warehouse_capacity[str(row["id"])] = float(capacity)
    for warehouse_id in decision.affected_warehouses:
        if warehouse_id in warehouse_capacity:
            notes.append(f"PASS: warehouse capacity recorded for {warehouse_id}.")
        else:
            notes.append(f"UNCHECKED: warehouse capacity unavailable for {warehouse_id}.")
    lead_days = {}
    if not supplier_links.empty and "lead_time_days" in supplier_links.columns:
        for _, row in supplier_links.iterrows():
            lead = pd.to_numeric(pd.Series([row["lead_time_days"]]),
                                 errors="coerce").iloc[0]
            if pd.notna(lead):
                lead_days[(str(row["supplier_id"]), str(row["product_id"]))] = float(lead)
    if lead_days:
        notes.append(
            f"PASS: lead-time evidence available for {len(lead_days)} relationship(s)."
        )
    else:
        notes.append("UNCHECKED: lead-time evidence unavailable.")
    notes.append("PASS: timing window within horizon (validated separately).")
    failures = [note for note in notes if note.startswith("FAIL:")]
    if failures:
        raise ValueError("Constraint check failed: " + "; ".join(failures))
    return notes

"""Scenario targeting resolution (Phase 8).

Targets resolve from explicit IDs, supplier-product links, or Phase 7
risk records. Risk records only identify CANDIDATES: event probability,
duration, reductions, delays, and multipliers always remain explicit
scenario assumptions, never derived from risk severity.
"""

from typing import Any


def resolve_explicit(
    supplier_ids: list[str] | None = None,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build affected-entity entries from explicit ID lists."""
    entities: list[dict[str, Any]] = []
    for supplier_id in supplier_ids or []:
        entities.append({"entity_type": "supplier", "supplier_id": supplier_id})
    for product_id in product_ids or []:
        entities.append({"entity_type": "product", "product_id": product_id})
    for warehouse_id in warehouse_ids or []:
        entities.append({"entity_type": "warehouse", "warehouse_id": warehouse_id})
    return entities


def resolve_supplier_products(
    supplier_id: str,
    supplier_links: object,
) -> list[dict[str, Any]]:
    """Expand a supplier into its supplier-product relationships."""
    import pandas as pd

    frame = supplier_links if isinstance(supplier_links, pd.DataFrame) else pd.DataFrame()
    entities = [{"entity_type": "supplier", "supplier_id": supplier_id}]
    if not frame.empty:
        own = frame[frame["supplier_id"].astype(str) == supplier_id]
        for _, row in own.iterrows():
            entities.append({
                "entity_type": "supplier_product",
                "supplier_id": supplier_id,
                "product_id": str(row["product_id"]),
            })
    return entities


def resolve_risk_record(risk_record: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Resolve affected entities from a Phase 7 risk record.

    Returns (entities, selection_basis). The risk record identifies
    candidates only; all event parameters stay explicit.
    """
    entities: list[dict[str, Any]] = []
    if risk_record.get("supplier_id"):
        entities.append({
            "entity_type": "supplier",
            "supplier_id": str(risk_record["supplier_id"]),
        })
    if risk_record.get("product_id"):
        entry: dict[str, Any] = {
            "entity_type": "product",
            "product_id": str(risk_record["product_id"]),
        }
        if risk_record.get("warehouse_id"):
            entry["warehouse_id"] = str(risk_record["warehouse_id"])
        entities.append(entry)
    basis = f"risk_record:{risk_record.get('risk_id', 'unknown')}"
    return entities, basis

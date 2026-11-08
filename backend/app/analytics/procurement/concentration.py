"""Descriptive supplier concentration (Phase 6).

Concentration is an EXPOSURE metric. It is never a recommendation to
diversify, switch, or add suppliers.
"""

import pandas as pd

from backend.app.analytics.procurement.types import (
    ProcurementIntelligenceConfig,
    SupplierConcentration,
)


def volume_shares(po_lines: pd.DataFrame, basis: str = "spend") -> list[SupplierConcentration]:
    """Share of procurement volume per supplier by spend or quantity."""
    if po_lines.empty:
        return []
    column = "line_total" if basis == "spend" else "quantity"
    totals = po_lines.groupby("supplier_id")[column].sum().astype(float)
    grand = float(totals.sum())
    if grand <= 0:
        return []
    return [
        SupplierConcentration(
            dimension="supplier", supplier_id=str(supplier), share=float(value) / grand,
            basis=basis,
            note="Share of observed generated procurement volume; descriptive only.",
        )
        for supplier, value in totals.sort_values(ascending=False).items()
    ]


def po_count_shares(po_lines: pd.DataFrame) -> list[SupplierConcentration]:
    """Share of purchase-order lines per supplier."""
    if po_lines.empty:
        return []
    counts = po_lines.groupby("supplier_id")["po_id"].nunique()
    grand = int(counts.sum())
    if grand <= 0:
        return []
    return [
        SupplierConcentration(
            dimension="supplier", supplier_id=str(supplier), share=int(value) / grand,
            basis="po_count", note="Share of PO lines; descriptive only.",
        )
        for supplier, value in counts.sort_values(ascending=False).items()
    ]


def dependency_classes(supplier_links: pd.DataFrame) -> dict[str, list[str]]:
    """Classify products by observed supplier coverage.

    Returns product lists keyed SINGLE_SUPPLIER | MULTI_SUPPLIER |
    NO_SUPPLIER_HISTORY. Products absent from every frame are UNKNOWN
    and reported by callers, not invented here.
    """
    classes: dict[str, list[str]] = {
        "SINGLE_SUPPLIER": [], "MULTI_SUPPLIER": [], "NO_SUPPLIER_HISTORY": [],
    }
    if supplier_links.empty:
        return classes
    counts = supplier_links.groupby("product_id")["supplier_id"].nunique()
    for product, total in counts.items():
        if total <= 0:
            classes["NO_SUPPLIER_HISTORY"].append(str(product))
        elif total == 1:
            classes["SINGLE_SUPPLIER"].append(str(product))
        else:
            classes["MULTI_SUPPLIER"].append(str(product))
    for key in classes:
        classes[key] = sorted(classes[key])
    return classes


def category_concentration(
    po_lines: pd.DataFrame, product_category: dict[str, str]
) -> list[SupplierConcentration]:
    """Top supplier spend share per product category (descriptive)."""
    if po_lines.empty:
        return []
    work = po_lines.copy()
    work["category"] = work["product_id"].map(product_category)
    work = work[work["category"].notna()]
    results: list[SupplierConcentration] = []
    for category, group in work.groupby("category"):
        totals = group.groupby("supplier_id")["line_total"].sum().astype(float)
        grand = float(totals.sum())
        if grand <= 0:
            continue
        top_supplier = str(totals.idxmax())
        results.append(SupplierConcentration(
            dimension=f"category:{category}", supplier_id=top_supplier,
            share=float(totals.max()) / grand, basis="spend",
            note="Top-supplier category share; descriptive only.",
        ))
    return results


def exposure_concentration(
    intelligence: list[object],
    supplier_products: dict[str, set[str]],
    config: ProcurementIntelligenceConfig,
) -> list[SupplierConcentration]:
    """Share of exposed series demand linked to each supplier.

    Links Phase 5 AT_RISK/CRITICAL/STOCKOUT series to suppliers through
    supplier-product relationships. Descriptive exposure, not sourcing
    advice.
    """
    _ = config
    exposed: dict[str, int] = {}
    total = 0
    for result in intelligence:
        health = result.health.health if result.health else "UNKNOWN"  # type: ignore[attr-defined]
        if health not in ("AT_RISK", "CRITICAL", "STOCKOUT"):
            continue
        total += 1
        product = result.product_id  # type: ignore[attr-defined]
        for supplier, products in supplier_products.items():
            if product in products:
                exposed[supplier] = exposed.get(supplier, 0) + 1
    if total <= 0:
        return []
    return [
        SupplierConcentration(
            dimension="exposed_series", supplier_id=supplier, share=count / total,
            basis="exposed_series_count",
            note="Share of exposed series linked to the supplier; descriptive only.",
        )
        for supplier, count in sorted(exposed.items(), key=lambda item: -item[1])
    ]

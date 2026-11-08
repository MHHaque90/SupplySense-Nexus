"""Dependency risk domain (Phase 7).

Structural exposure: single-supplier products, suppliers carrying many
exposed products, warehouses on narrow supplier sets, and category
concentration. Dependency is an exposure — never a diversification
recommendation.
"""

from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    risk_id,
)


def product_dependency(
    product_id: str,
    supplier_ids: list[str],
    exposed_warehouses: int,
    analysis_date: str,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess structural dependency risk for one product."""
    del config
    entity = product_id
    if not supplier_ids:
        return RiskRecord(
            risk_id=risk_id("dependency", "product", entity, analysis_date),
            domain="dependency", entity_type="product", entity_id=entity,
            product_id=product_id, analysis_date=analysis_date,
            state="UNKNOWN", severity="UNKNOWN",
            evidence=["No supplier relationships observed for the product."],
            missing_evidence=["supplier_relationships"],
            provenance={"data_source": "synthetic"},
            explanation="Dependency risk is UNKNOWN: no supplier history exists.",
        )
    if len(supplier_ids) == 1:
        return RiskRecord(
            risk_id=risk_id("dependency", "product", entity, analysis_date),
            domain="dependency", entity_type="product", entity_id=entity,
            product_id=product_id, analysis_date=analysis_date,
            state="HIGH", severity="HIGH",
            evidence=[
                f"Single-supplier dependency on {supplier_ids[0]}.",
                f"Exposed in {exposed_warehouses} warehouse(s).",
            ],
            metrics={"supplier_count": 1.0, "exposed_warehouses": float(exposed_warehouses)},
            supporting_records=[f"supplier_product:{supplier_ids[0]}:{product_id}"],
            provenance={"data_source": "synthetic"},
            explanation=(
                f"Product {product_id} has a single-supplier dependency; "
                "exposure description only, no sourcing change implied."
            ),
        )
    return RiskRecord(
        risk_id=risk_id("dependency", "product", entity, analysis_date),
        domain="dependency", entity_type="product", entity_id=entity,
        product_id=product_id, analysis_date=analysis_date,
        state="LOW", severity="LOW",
        evidence=[f"{len(supplier_ids)} supplying relationships observed."],
        metrics={"supplier_count": float(len(supplier_ids))},
        provenance={"data_source": "synthetic"},
        explanation=f"Product {product_id} is multi-sourced across {len(supplier_ids)} suppliers.",
    )


def supplier_fanout(
    supplier_id: str,
    exposed_products: list[str],
    total_products: int,
    analysis_date: str,
) -> RiskRecord:
    """Assess how much exposure flows through one supplier."""
    if total_products <= 0 or not exposed_products:
        return RiskRecord(
            risk_id=risk_id("dependency", "supplier", supplier_id, analysis_date),
            domain="dependency", entity_type="supplier", entity_id=supplier_id,
            supplier_id=supplier_id, analysis_date=analysis_date,
            state="LOW", severity="LOW",
            evidence=["No exposed products linked to this supplier."],
            metrics={"exposed_products": 0.0},
            provenance={"data_source": "synthetic"},
            explanation="No exposure flows through this supplier in the observed records.",
        )
    share = len(exposed_products) / total_products
    state = "HIGH" if share >= 0.5 else "MODERATE"
    return RiskRecord(
        risk_id=risk_id("dependency", "supplier", supplier_id, analysis_date),
        domain="dependency", entity_type="supplier", entity_id=supplier_id,
        supplier_id=supplier_id, analysis_date=analysis_date,
        state=state, severity=state,
        evidence=[
            f"{len(exposed_products)} of {total_products} linked products show exposure.",
        ],
        metrics={"exposed_products": float(len(exposed_products)), "share": share},
        provenance={"data_source": "synthetic"},
        explanation=(
            f"Exposure concentration through this supplier is {state.lower()}: "
            f"{share:.0%} of linked products show exposure."
        ),
    )


def warehouse_breadth(
    warehouse_id: str,
    supplier_ids: list[str],
    analysis_date: str,
) -> RiskRecord:
    """Assess how narrow a warehouse's supplier set is."""
    count = len(set(supplier_ids))
    if count == 0:
        state: str = "UNKNOWN"
        evidence = ["No supplier links observed for this warehouse."]
    elif count == 1:
        state = "HIGH"
        evidence = ["Warehouse served by a single observed supplier."]
    elif count == 2:
        state = "MODERATE"
        evidence = ["Warehouse served by two observed suppliers."]
    else:
        state = "LOW"
        evidence = [f"Warehouse served by {count} observed suppliers."]
    return RiskRecord(
        risk_id=risk_id("dependency", "warehouse", warehouse_id, analysis_date),
        domain="dependency", entity_type="warehouse", entity_id=warehouse_id,
        warehouse_id=warehouse_id, analysis_date=analysis_date,
        state=state, severity=state, evidence=evidence,
        metrics={"supplier_count": float(count)},
        missing_evidence=[] if count else ["supplier_links"],
        provenance={"data_source": "synthetic"},
        explanation=f"Warehouse supplier breadth is {state.lower()} ({count} suppliers).",
    )

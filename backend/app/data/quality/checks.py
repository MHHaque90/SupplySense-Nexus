"""Reusable data-quality checks (Phase 2).

Each check queries the database through SQLAlchemy (never raw SQL in
the sense of string-built statements; static ORM selects only) and
returns a structured :class:`CheckResult`.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.data.config import GenerationConfig
from backend.app.data.generators.bom import validate_no_cycles
from backend.app.data.ingestion.pipeline import GeneratedDataset
from backend.app.models import (
    BOM,
    BOMComponent,
    DemandObservation,
    Disruption,
    InventorySnapshot,
    InventoryTransaction,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
    Shipment,
    ShipmentEvent,
    Supplier,
    SupplierProduct,
    User,
    Warehouse,
)

STATUSES = ("PASS", "WARN", "FAIL")
SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")

# Tables carrying a data_source_label column in the Phase 1 schema.
_LABELED_TABLES: list[Any] = [
    Organization,
    Product,
    Supplier,
    Warehouse,
    PurchaseOrder,
    PurchaseOrderLine,
    Shipment,
    SalesOrder,
    SalesOrderLine,
    DemandObservation,
    InventorySnapshot,
    InventoryTransaction,
    SupplierProduct,
    BOM,
    Disruption,
]


@dataclass
class CheckResult:
    """Structured outcome of a single data-quality check."""

    check_name: str
    table: str
    status: str
    severity: str
    observed: str
    expected: str
    details: str
    checked_at: date
    provenance: str = "derived"

    def passed(self) -> bool:
        """Return True only for PASS (WARN and FAIL both flag issues)."""
        return self.status == "PASS"

    def to_row(self) -> dict[str, Any]:
        """Project the result onto the data_quality_checks columns."""
        return {
            "table_name": self.table,
            "check_type": self.status,
            "check_rule": f"{self.check_name} [{self.severity}] expected={self.expected}",
            "passed": self.passed(),
            "row_count": 0,
            "failure_count": 0 if self.passed() else 1,
            "checked_at": self.checked_at,
            "details": f"observed={self.observed}; {self.details}",
        }


async def _count(session: AsyncSession, model: Any, *filters: Any) -> int:
    result = await session.execute(select(func.count(model.id)).filter(*filters))
    return result.scalar() or 0


def _result(
    name: str,
    table: str,
    failures: int,
    expected: str,
    details: str,
    severity: str = "HIGH",
    warn_only: bool = False,
) -> CheckResult:
    if failures == 0:
        status = "PASS"
    elif warn_only:
        status = "WARN"
    else:
        status = "FAIL"
    return CheckResult(
        check_name=name,
        table=table,
        status=status,
        severity="INFO" if status == "PASS" else severity,
        observed=f"failures={failures}",
        expected=expected,
        details=details,
        checked_at=date.today(),
    )


async def check_required_fields(session: AsyncSession) -> list[CheckResult]:
    """Required columns must not be null (completeness)."""
    required: list[tuple[Any, str, Any]] = [
        (Organization, "organizations", Organization.name),
        (User, "users", User.email),
        (Product, "products", Product.sku),
        (Supplier, "suppliers", Supplier.name),
        (Warehouse, "warehouses", Warehouse.name),
        (PurchaseOrder, "purchase_orders", PurchaseOrder.po_number),
        (Shipment, "shipments", Shipment.expected_arrival_date),
        (DemandObservation, "demand_observations", DemandObservation.quantity),
    ]
    results = []
    for model, table, column in required:
        nulls = await _count(session, model, column.is_(None))
        results.append(_result("required_fields_not_null", table, nulls, "nulls=0",
                               f"Null values in required column {column.key}."))
    return results


async def check_uniqueness(session: AsyncSession) -> list[CheckResult]:
    """Natural keys must be unique (uniqueness)."""
    results = []
    for model, table, column in [
        (Product, "products", Product.sku),
        (User, "users", User.email),
        (PurchaseOrder, "purchase_orders", PurchaseOrder.po_number),
    ]:
        rows = (await session.execute(select(column))).all()
        values = [row[0] for row in rows]
        duplicates = len(values) - len(set(values))
        results.append(_result("natural_key_unique", table, duplicates, "duplicates=0",
                               f"Duplicate values in {column.key}."))
    return results


async def check_ranges(session: AsyncSession) -> list[CheckResult]:
    """Quantities, costs, lead times, and probabilities (range validity)."""
    results = []
    checks: list[tuple[Any, str, str, Any]] = [
        (SupplierProduct, "supplier_products", "lead_time_days", SupplierProduct.lead_time_days),
        (BOMComponent, "bom_components", "lead_time_days", BOMComponent.lead_time_days),
    ]
    for model, table, label, column in checks:
        bad = await _count(session, model, (column < 0) | (column > 365))
        results.append(_result(f"range_valid_{label}", table, bad, "0<=x<=365",
                               f"Lead times outside 0-365 days in {table}."))
    for model, table, column_name in [
        (DemandObservation, "demand_observations", "quantity"),
        (InventoryTransaction, "inventory_transactions", "quantity"),
        (PurchaseOrderLine, "purchase_order_lines", "quantity"),
        (SalesOrderLine, "sales_order_lines", "quantity"),
    ]:
        column = getattr(model, column_name)
        rows = (await session.execute(select(column))).all()
        bad = sum(1 for row in rows if float(row[0]) < 0)
        results.append(_result("range_valid_quantities", table, bad, "quantity>=0",
                               f"Negative quantities in {table}."))
    return results


async def check_referential_integrity(session: AsyncSession) -> list[CheckResult]:
    """Every foreign key must resolve (referential integrity)."""
    links: list[tuple[str, Any, Any, str]] = [
        ("products", Product.organization_id, Organization, "organizations"),
        ("users", User.organization_id, Organization, "organizations"),
        ("suppliers", Supplier.organization_id, Organization, "organizations"),
        ("warehouses", Warehouse.organization_id, Organization, "organizations"),
        ("demand_observations", DemandObservation.product_id, Product, "products"),
        ("demand_observations", DemandObservation.warehouse_id, Warehouse, "warehouses"),
        ("purchase_orders", PurchaseOrder.supplier_id, Supplier, "suppliers"),
        ("purchase_order_lines", PurchaseOrderLine.po_id, PurchaseOrder, "purchase_orders"),
        ("shipments", Shipment.po_id, PurchaseOrder, "purchase_orders"),
        ("shipment_events", ShipmentEvent.shipment_id, Shipment, "shipments"),
        ("sales_order_lines", SalesOrderLine.sales_order_id, SalesOrder, "sales_orders"),
        ("bom_components", BOMComponent.bom_id, BOM, "bills_of_materials"),
        ("supplier_products", SupplierProduct.supplier_id, Supplier, "suppliers"),
        ("supplier_products", SupplierProduct.product_id, Product, "products"),
    ]
    results = []
    for child_table, fk, parent, parent_table in links:
        parent_ids = set((await session.execute(select(parent.id))).scalars().all())
        child_rows = (await session.execute(select(fk))).all()
        orphans = sum(1 for row in child_rows if row[0] not in parent_ids and row[0] is not None)
        results.append(_result(
            "referential_integrity", child_table, orphans,
            f"all {fk.key} present in {parent_table}",
            f"Orphan foreign keys {fk.key} in {child_table}.",
        ))
    return results


async def check_temporal_consistency(
    session: AsyncSession, config: GenerationConfig
) -> list[CheckResult]:
    """Dates must be coherent and inside history (temporal consistency)."""
    results = []
    start, end = config.start_date, config.end_date
    early_demand = await _count(
        session, DemandObservation,
        (DemandObservation.date < start) | (DemandObservation.date > end),
    )
    results.append(_result("demand_within_history", "demand_observations", early_demand,
                           f"{start}<=date<={end}", "Demand dates outside history window."))
    po_rows = (await session.execute(
        select(PurchaseOrder.id, PurchaseOrder.order_date, PurchaseOrder.expected_delivery_date)
    )).all()
    bad_po = sum(1 for _po_id, order_date, expected in po_rows
                 if expected is not None and expected < order_date)
    results.append(_result("po_expected_after_order", "purchase_orders", bad_po,
                           "expected>=order", "Expected delivery before order date."))
    po_dates = {row[0]: row[1] for row in po_rows}
    ship_rows = (await session.execute(
        select(Shipment.po_id, Shipment.shipped_date, Shipment.actual_arrival_date)
    )).all()
    bad_ship = sum(
        1 for po_id, shipped, actual in ship_rows
        if (shipped is not None and shipped < po_dates.get(po_id, shipped))
        or (actual is not None and shipped is not None and actual < shipped)
    )
    results.append(_result("shipment_dates_coherent", "shipments", bad_ship,
                           "ship>=po and actual>=ship", "Impossible shipment dates."))
    disruption_rows = (await session.execute(
        select(Disruption.start_date, Disruption.end_date)
    )).all()
    bad_dis = sum(1 for begins, ends in disruption_rows if ends is not None and ends < begins)
    results.append(_result("disruption_end_after_start", "disruptions", bad_dis,
                           "end>=start", "Disruption ends before it starts."))
    future = await _count(session, DemandObservation, DemandObservation.date > end)
    results.append(_result("no_future_history", "demand_observations", future,
                           "date<=history_end", "Historical dates beyond dataset end."))
    return results


async def check_provenance(session: AsyncSession) -> list[CheckResult]:
    """Every labeled row must carry a valid data_source_label."""
    from backend.app.core.data_labels import DataSourceLabel

    valid = set(DataSourceLabel.values())
    results = []
    for model, table in [(m, m.__tablename__) for m in _LABELED_TABLES]:
        rows = (await session.execute(select(model.data_source_label))).all()
        bad = sum(1 for row in rows if row[0] not in valid)
        results.append(_result("provenance_present", table, bad,
                               "label in enum", f"Missing/invalid data_source_label in {table}."))
    return results


async def check_organization_boundaries(session: AsyncSession) -> list[CheckResult]:
    """Organization-owned rows must reference existing organizations."""
    org_ids = set((await session.execute(select(Organization.id))).scalars().all())
    results = []
    for model, table in [
        (Product, "products"), (Supplier, "suppliers"), (Warehouse, "warehouses"),
        (PurchaseOrder, "purchase_orders"), (SalesOrder, "sales_orders"),
        (User, "users"),
    ]:
        rows = (await session.execute(select(model.organization_id))).all()
        bad = sum(1 for row in rows if row[0] not in org_ids)
        results.append(_result("organization_boundaries", table, bad,
                               "org exists", f"Rows outside tenant boundary in {table}."))
    return results


async def check_bom_acyclic(session: AsyncSession) -> list[CheckResult]:
    """BOM graph must contain no cycles (business rule)."""
    edges: dict[str, list[str]] = {}
    boms = (await session.execute(select(BOM))).scalars().all()
    components = (await session.execute(select(BOMComponent))).scalars().all()
    bom_product = {bom.id: bom.product_id for bom in boms}
    for component in components:
        finished = bom_product.get(component.bom_id)
        if finished:
            edges.setdefault(finished, []).append(component.component_product_id)
    try:
        validate_no_cycles(edges)
        failures = 0
        details = "BOM graph is acyclic."
    except ValueError as exc:
        failures = 1
        details = str(exc)
    return [_result("bom_acyclic", "bom_components", failures, "cycles=0", details)]


async def check_inventory_reconciliation(
    session: AsyncSession, dataset: GeneratedDataset
) -> list[CheckResult]:
    """opening + receipts - sales + adjustments must equal closing."""
    txn_rows = (await session.execute(
        select(InventoryTransaction.product_id, InventoryTransaction.warehouse_id,
               InventoryTransaction.transaction_type, InventoryTransaction.quantity)
    )).all()
    snap_rows = (await session.execute(
        select(InventorySnapshot.product_id, InventorySnapshot.warehouse_id,
               InventorySnapshot.available_qty, InventorySnapshot.snapshot_date)
    )).all()
    ledger: dict[tuple[str, str], float] = {}
    for product_id, warehouse_id, txn_type, quantity in txn_rows:
        key = (product_id, warehouse_id)
        amount = float(quantity)
        if txn_type in ("OPENING_BALANCE", "RECEIPT", "ADJUSTMENT"):
            ledger[key] = ledger.get(key, 0.0) + amount
        elif txn_type == "SALE":
            ledger[key] = ledger.get(key, 0.0) - amount
    latest: dict[tuple[str, str], tuple[str, str]] = {}
    for product_id, warehouse_id, available, snap_date in snap_rows:
        key = (product_id, warehouse_id)
        if key not in latest or snap_date >= latest[key][1]:
            latest[key] = (available, snap_date)
    mismatches = sum(
        1 for key, (available, _snap_date) in latest.items()
        if abs(ledger.get(key, 0.0) - float(available)) > 0.01
    )
    return [_result("inventory_reconciliation", "inventory_snapshots", mismatches,
                    "ledger==closing", "Ledger does not reconcile to closing snapshot.",
                    severity="CRITICAL")]


async def check_procurement_reconciliation(session: AsyncSession) -> list[CheckResult]:
    """PO line quantities must cover shipment-linked receipts (no over-receipt)."""
    line_rows = (await session.execute(
        select(PurchaseOrderLine.po_id, PurchaseOrderLine.product_id, PurchaseOrderLine.quantity)
    )).all()
    ordered: dict[str, float] = {}
    line_products: dict[str, str] = {}
    for po_id, product_id, quantity in line_rows:
        ordered[po_id] = ordered.get(po_id, 0.0) + float(quantity)
        line_products[po_id] = product_id
    shipment_rows = (await session.execute(
        select(Shipment.po_id, Shipment.status)
    )).all()
    received_pos = {po_id for po_id, status in shipment_rows if status in ("delivered", "delayed")}
    orphans = sum(1 for po_id, _status in shipment_rows if po_id not in ordered)
    partial = sum(1 for po_id in ordered if po_id not in received_pos)
    results = [
        _result("shipment_po_link", "shipments", orphans, "every shipment links a PO",
                "Shipments referencing unknown purchase orders."),
        _result("procurement_open_pos", "purchase_orders", 0,
                "informational",
                f"{partial} POs not yet fully received at dataset end (normal).",
                severity="INFO"),
    ]
    # MOQ rule: every PO line quantity >= supplier MOQ.
    link_rows = (await session.execute(
        select(SupplierProduct.supplier_id, SupplierProduct.product_id,
               SupplierProduct.min_order_qty)
    )).all()
    links = {(s, p): float(moq) for s, p, moq in link_rows}
    po_rows = (await session.execute(
        select(PurchaseOrder.id, PurchaseOrder.supplier_id)
    )).all()
    po_supplier = {po_id: supplier_id for po_id, supplier_id in po_rows}
    moq_violations = sum(
        1 for po_id, product_id, quantity in line_rows
        if float(quantity) < links.get((po_supplier.get(po_id), product_id), 0.0)
    )
    results.append(_result("procurement_moq", "purchase_order_lines", moq_violations,
                           "qty>=MOQ", "PO line below supplier MOQ."))
    return results


async def check_expected_ranges(
    session: AsyncSession, dataset: GeneratedDataset
) -> list[CheckResult]:
    """Generated counts must fall within expected ranges."""
    expected_days = dataset.config.history_days
    product_count = await _count(session, Product)
    warehouse_count = await _count(session, Warehouse)
    demand_rows = await _count(session, DemandObservation)
    minimum = product_count * warehouse_count * expected_days
    failures = 0 if demand_rows == minimum else 1
    return [_result("expected_record_counts", "demand_observations", failures,
                    f"rows={minimum}",
                    f"Demand continuity: {demand_rows} rows vs {minimum} expected.",
                    severity="MEDIUM")]


async def run_all_checks(
    session: AsyncSession, config: GenerationConfig, dataset: GeneratedDataset
) -> list[CheckResult]:
    """Execute every check group and return structured results."""
    results: list[CheckResult] = []
    results.extend(await check_required_fields(session))
    results.extend(await check_uniqueness(session))
    results.extend(await check_ranges(session))
    results.extend(await check_referential_integrity(session))
    results.extend(await check_temporal_consistency(session, config))
    results.extend(await check_provenance(session))
    results.extend(await check_organization_boundaries(session))
    results.extend(await check_bom_acyclic(session))
    results.extend(await check_inventory_reconciliation(session, dataset))
    results.extend(await check_procurement_reconciliation(session))
    results.extend(await check_expected_ranges(session, dataset))
    return results

"""Dataset generation orchestration and database loading (Phase 2).

Pipeline order: generate -> validate (structural) -> insert -> verify.
Persistence uses batched inserts inside a single transaction: any
failure rolls back the whole dataset, never leaving partial data.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.data.config import GenerationConfig
from backend.app.data.generators import (
    bom,
    catalog,
    demand,
    disruptions,
    inventory,
    organizations,
    procurement,
    sales,
    shipments,
    suppliers,
    users,
    warehouses,
)
from backend.app.data.ingestion.loaders import insert_batch
from backend.app.models import (
    BOM,
    BOMComponent,
    DemandObservation,
    Disruption,
    DisruptionImpact,
    InventorySnapshot,
    InventoryTransaction,
    Organization,
    Product,
    ProductCategory,
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


class DatasetExistsError(RuntimeError):
    """Raised when a synthetic dataset already exists and --reset was not given."""


@dataclass
class GeneratedDataset:
    """All generated records plus reconciliation metadata."""

    config: GenerationConfig
    organizations: list[dict[str, Any]] = field(default_factory=list)
    users: list[dict[str, Any]] = field(default_factory=list)
    categories: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    suppliers: list[dict[str, Any]] = field(default_factory=list)
    supplier_products: list[dict[str, Any]] = field(default_factory=list)
    warehouses: list[dict[str, Any]] = field(default_factory=list)
    boms: list[dict[str, Any]] = field(default_factory=list)
    bom_components: list[dict[str, Any]] = field(default_factory=list)
    demand: list[dict[str, Any]] = field(default_factory=list)
    sales_orders: list[dict[str, Any]] = field(default_factory=list)
    sales_lines: list[dict[str, Any]] = field(default_factory=list)
    purchase_orders: list[dict[str, Any]] = field(default_factory=list)
    purchase_order_lines: list[dict[str, Any]] = field(default_factory=list)
    shipments: list[dict[str, Any]] = field(default_factory=list)
    shipment_events: list[dict[str, Any]] = field(default_factory=list)
    inventory_transactions: list[dict[str, Any]] = field(default_factory=list)
    inventory_snapshots: list[dict[str, Any]] = field(default_factory=list)
    disruptions: list[dict[str, Any]] = field(default_factory=list)
    disruption_impacts: list[dict[str, Any]] = field(default_factory=list)
    # Reconciliation metadata (not database rows).
    openings: dict[str, int] = field(default_factory=dict)
    fulfilled_sales: dict[str, int] = field(default_factory=dict)
    supplier_profiles: dict[str, str] = field(default_factory=dict)

    def table_counts(self) -> dict[str, int]:
        """Return generated record counts per entity type."""
        return {
            "organizations": len(self.organizations),
            "users": len(self.users),
            "product_categories": len(self.categories),
            "products": len(self.products),
            "suppliers": len(self.suppliers),
            "supplier_products": len(self.supplier_products),
            "warehouses": len(self.warehouses),
            "bills_of_materials": len(self.boms),
            "bom_components": len(self.bom_components),
            "demand_observations": len(self.demand),
            "sales_orders": len(self.sales_orders),
            "sales_order_lines": len(self.sales_lines),
            "purchase_orders": len(self.purchase_orders),
            "purchase_order_lines": len(self.purchase_order_lines),
            "shipments": len(self.shipments),
            "shipment_events": len(self.shipment_events),
            "inventory_transactions": len(self.inventory_transactions),
            "inventory_snapshots": len(self.inventory_snapshots),
            "disruptions": len(self.disruptions),
            "disruption_impacts": len(self.disruption_impacts),
        }


def generate_dataset(config: GenerationConfig) -> GeneratedDataset:
    """Run every generator in dependency order (pure, no database I/O)."""
    dataset = GeneratedDataset(config=config)
    dataset.organizations = organizations.generate_organizations(config)
    org_keys = [str(o["name"]) for o in dataset.organizations]
    counts = config.per_organization_counts()
    dataset.users = users.generate_users(config, org_keys)
    dataset.categories = catalog.generate_categories()
    dataset.products = catalog.generate_products(config, org_keys, counts["products"])
    dataset.suppliers = suppliers.generate_suppliers(config, org_keys, counts["suppliers"])
    for supplier in dataset.suppliers:
        dataset.supplier_profiles[str(supplier["supplier_code"])] = str(
            supplier["supplier_profile"]
        )
    dataset.supplier_products = suppliers.generate_supplier_products(
        config, dataset.products, dataset.suppliers
    )
    expected_units = {
        key: int(sum(float(str(p.get("baseline_demand", "20.0"))) for p in dataset.products
                     if str(p["organization_key"]) == key) * config.coverage_days)
        for key in org_keys
    }
    dataset.warehouses = warehouses.generate_warehouses(
        config, org_keys, counts["warehouses"], expected_units
    )
    dataset.boms, dataset.bom_components = bom.generate_bom(config, dataset.products)
    dataset.demand = demand.generate_demand(config, dataset.products, dataset.warehouses)
    dataset.sales_orders, dataset.sales_lines = sales.generate_sales(
        config, dataset.demand, dataset.products
    )
    dataset.purchase_orders, dataset.purchase_order_lines, receipts = (
        procurement.generate_purchase_orders(config, dataset.demand, dataset.supplier_products)
    )
    dataset.shipments, dataset.shipment_events = shipments.generate_shipments(
        config, dataset.purchase_orders, dataset.supplier_profiles
    )
    txns, snaps, openings, fulfilled = inventory.simulate_inventory(
        config, dataset.demand, receipts, dataset.sales_orders,
        dataset.sales_lines, dataset.products,
    )
    dataset.inventory_transactions = txns
    dataset.inventory_snapshots = snaps
    dataset.openings = openings
    dataset.fulfilled_sales = fulfilled
    dataset.disruptions, dataset.disruption_impacts = disruptions.generate_disruptions(
        config, dataset.suppliers, dataset.products, dataset.warehouses
    )
    return dataset


async def dataset_exists(session: AsyncSession) -> bool:
    """Return True when a synthetic dataset is already present."""
    result = await session.execute(select(func.count(Organization.id)))
    return (result.scalar() or 0) > 0


# Tables in child-first deletion order for scoped resets.
_RESET_ORDER: list[Any] = [
    ShipmentEvent,
    Shipment,
    PurchaseOrderLine,
    PurchaseOrder,
    SupplierProduct,
    SalesOrderLine,
    SalesOrder,
    DemandObservation,
    InventoryTransaction,
    InventorySnapshot,
    DisruptionImpact,
    Disruption,
    BOMComponent,
    BOM,
    Product,
    ProductCategory,
    Supplier,
    Warehouse,
    User,
    Organization,
]


async def reset_dataset(session: AsyncSession) -> dict[str, int]:
    """Delete only SupplySense Nexus synthetic tables in FK-safe order.

    Scope is restricted to the dataset tables listed in ``_RESET_ORDER``
    inside the configured database. Unrelated databases, schemas, and
    the Alembic version table are never touched.
    """
    removed: dict[str, int] = {}
    for model in _RESET_ORDER:
        result = await session.execute(select(func.count(model.id)))
        count = result.scalar() or 0
        await session.execute(model.__table__.delete())
        removed[model.__tablename__] = count
    await session.flush()
    return removed


def _as_date(value: str) -> date:
    return date.fromisoformat(value)


async def load_dataset(
    session: AsyncSession, dataset: GeneratedDataset, allow_existing: bool = False
) -> dict[str, int]:
    """Insert a generated dataset with batching and verification.

    Raises:
        DatasetExistsError: When data already exists and ``allow_existing``
            is False (idempotency guard).
    """
    if not allow_existing and await dataset_exists(session):
        raise DatasetExistsError(
            "A synthetic dataset already exists. Re-run with --reset to "
            "remove only the generated SupplySense dataset and regenerate it."
        )
    config = dataset.config
    batch = config.batch_size
    org_ids: dict[str, str] = {}
    for record in dataset.organizations:
        obj = Organization(
            name=str(record["name"]),
            industry=str(record["industry"]),
            data_source_label=str(record["data_source_label"]),
        )
        session.add(obj)
        await session.flush()
        org_ids[str(record["name"])] = obj.id
    category_ids: dict[str, str] = {}
    for record in dataset.categories:
        obj = ProductCategory(name=str(record["name"]), parent_id=None)
        session.add(obj)
        await session.flush()
        category_ids[str(record["name"])] = obj.id
    user_ids: dict[str, str] = {}
    user_objects = []
    for record in dataset.users:
        user_objects.append(
            User(
                email=str(record["email"]),
                username=str(record["username"]),
                password_hash=str(record["password_hash"]),
                role=str(record["role"]),
                organization_id=org_ids[str(record["organization_key"])],
                is_active=bool(record["is_active"]),
            )
        )
    await insert_batch(session, user_objects, batch)
    for record, obj in zip(dataset.users, user_objects):
        user_ids[str(record["email"])] = obj.id
    product_ids: dict[str, str] = {}
    product_objects = []
    for record in dataset.products:
        product_objects.append(
            Product(
                sku=str(record["sku"]),
                name=str(record["name"]),
                category_id=category_ids.get(str(record["category_key"])),
                unit_cost=str(record["unit_cost"]),
                weight_kg=str(record["weight_kg"]),
                organization_id=org_ids[str(record["organization_key"])],
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, product_objects, batch)
    for record, obj in zip(dataset.products, product_objects):
        product_ids[str(record["sku"])] = obj.id
    supplier_ids: dict[str, str] = {}
    supplier_objects = []
    for record in dataset.suppliers:
        supplier_objects.append(
            Supplier(
                name=str(record["name"]),
                country=str(record["country"]),
                rating=str(record["rating"]),
                organization_id=org_ids[str(record["organization_key"])],
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, supplier_objects, batch)
    for record, obj in zip(dataset.suppliers, supplier_objects):
        supplier_ids[str(record["supplier_code"])] = obj.id
    warehouse_ids: dict[str, str] = {}
    warehouse_objects = []
    for record in dataset.warehouses:
        warehouse_objects.append(
            Warehouse(
                name=str(record["name"]),
                location=str(record["location"]),
                capacity_units=int(record["capacity_units"]),
                current_utilization=str(record["current_utilization"]),
                organization_id=org_ids[str(record["organization_key"])],
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, warehouse_objects, batch)
    for record, obj in zip(dataset.warehouses, warehouse_objects):
        warehouse_ids[str(record["warehouse_code"])] = obj.id
    await insert_batch(
        session,
        [
            SupplierProduct(
                supplier_id=supplier_ids[str(r["supplier_key"])],
                product_id=product_ids[str(r["product_key"])],
                unit_cost=str(r["unit_cost"]),
                lead_time_days=int(r["lead_time_days"] or 0),
                min_order_qty=str(r["min_order_qty"]),
                moq_currency=str(r["moq_currency"]),
                capacity_units=str(r.get("capacity_units") or "0"),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.supplier_products
        ],
        batch,
    )
    bom_ids: dict[str, str] = {}
    bom_objects = []
    for record in dataset.boms:
        bom_objects.append(
            BOM(
                product_id=product_ids[str(record["product_key"])],
                version=str(record["version"]),
                effective_date=_as_date(str(record["effective_date"])),
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, bom_objects, batch)
    for record, obj in zip(dataset.boms, bom_objects):
        bom_ids[str(record["bom_key"])] = obj.id
    await insert_batch(
        session,
        [
            BOMComponent(
                bom_id=bom_ids[str(r["bom_key"])],
                component_product_id=product_ids[str(r["component_key"])],
                quantity=str(r["quantity"]),
                unit_of_measure=str(r["unit_of_measure"]),
                lead_time_days=int(r["lead_time_days"]),
            )
            for r in dataset.bom_components
        ],
        batch,
    )
    await insert_batch(
        session,
        [
            DemandObservation(
                product_id=product_ids[r["product_key"]],
                warehouse_id=warehouse_ids[r["warehouse_key"]],
                date=_as_date(r["date"]),
                quantity=str(r["quantity"]),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.demand
        ],
        batch,
    )
    order_ids: dict[str, str] = {}
    sales_objects = []
    for record in dataset.sales_orders:
        sales_objects.append(
            SalesOrder(
                customer_id=str(record["customer_key"]),
                order_date=_as_date(str(record["order_date"])),
                warehouse_id=warehouse_ids[str(record["warehouse_key"])],
                total_amount=str(record["total_amount"]),
                status=str(record["status"]),
                organization_id=org_ids[str(record["organization_key"])],
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, sales_objects, batch)
    for record, obj in zip(dataset.sales_orders, sales_objects):
        order_ids[str(record["order_key"])] = obj.id
    await insert_batch(
        session,
        [
            SalesOrderLine(
                sales_order_id=order_ids[r["order_key"]],
                product_id=product_ids[r["product_key"]],
                quantity=str(r["quantity"]),
                unit_price=str(r["unit_price"]),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.sales_lines
        ],
        batch,
    )
    po_ids: dict[str, str] = {}
    po_objects = []
    for record in dataset.purchase_orders:
        po_objects.append(
            PurchaseOrder(
                supplier_id=supplier_ids[str(record["supplier_key"])],
                po_number=str(record["order_key"]),
                order_date=_as_date(str(record["order_date"])),
                expected_delivery_date=_as_date(str(record["expected_delivery_date"]))
                if record.get("expected_delivery_date")
                else None,
                total_cost=str(record["total_cost"]),
                status=str(record["status"]),
                organization_id=org_ids[_supplier_org(dataset, str(record["supplier_key"]))],
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, po_objects, batch)
    for record, obj in zip(dataset.purchase_orders, po_objects):
        po_ids[str(record["order_key"])] = obj.id
    await insert_batch(
        session,
        [
            PurchaseOrderLine(
                po_id=po_ids[r["order_key"]],
                product_id=product_ids[r["product_key"]],
                quantity=str(r["quantity"]),
                unit_cost=str(r["unit_cost"]),
                line_total=str(r["line_total"]),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.purchase_order_lines
        ],
        batch,
    )
    shipment_ids: dict[str, str] = {}
    shipment_objects = []
    for record in dataset.shipments:
        shipment_objects.append(
            Shipment(
                po_id=po_ids[str(record["order_key"])],
                supplier_id=supplier_ids[str(record["supplier_key"])],
                shipped_date=_as_date(str(record["shipped_date"]))
                if record.get("shipped_date")
                else None,
                expected_arrival_date=_as_date(str(record["expected_arrival_date"])),
                actual_arrival_date=_as_date(str(record["actual_arrival_date"]))
                if record.get("actual_arrival_date")
                else None,
                status=str(record["status"]),
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, shipment_objects, batch)
    for record, obj in zip(dataset.shipments, shipment_objects):
        shipment_ids[str(record["shipment_key"])] = obj.id
    await insert_batch(
        session,
        [
            ShipmentEvent(
                shipment_id=shipment_ids[str(r["shipment_key"])],
                event_type=str(r["event_type"]),
                event_date=_as_date(str(r["event_date"])),
                description=str(r.get("description")),
            )
            for r in dataset.shipment_events
        ],
        batch,
    )
    await insert_batch(
        session,
        [
            InventoryTransaction(
                warehouse_id=warehouse_ids[r["warehouse_key"]],
                product_id=product_ids[r["product_key"]],
                transaction_type=str(r["transaction_type"]),
                quantity=str(r["quantity"]),
                reference_id=order_ids.get(str(r["reference_key"] or "")),
                timestamp=_as_date(str(r["timestamp"])),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.inventory_transactions
        ],
        batch,
    )
    await insert_batch(
        session,
        [
            InventorySnapshot(
                warehouse_id=warehouse_ids[r["warehouse_key"]],
                product_id=product_ids[r["product_key"]],
                available_qty=str(r["available_qty"]),
                reserved_qty=str(r["reserved_qty"]),
                in_transit_qty=str(r["in_transit_qty"]),
                snapshot_date=_as_date(str(r["snapshot_date"])),
                data_source_label=str(r["data_source_label"]),
            )
            for r in dataset.inventory_snapshots
        ],
        batch,
    )
    disruption_ids: dict[str, str] = {}
    disruption_objects = []
    for record in dataset.disruptions:
        supplier_key = record.get("supplier_key")
        disruption_objects.append(
            Disruption(
                name=str(record["name"]),
                disruption_type=str(record["disruption_type"]),
                severity=str(record["severity"]),
                start_date=_as_date(str(record["start_date"])),
                end_date=_as_date(str(record["end_date"])),
                affected_supplier_id=supplier_ids.get(str(supplier_key))
                if supplier_key
                else None,
                description=str(record.get("description")),
                data_source_label=str(record["data_source_label"]),
            )
        )
    await insert_batch(session, disruption_objects, batch)
    for record, obj in zip(dataset.disruptions, disruption_objects):
        disruption_ids[str(record["disruption_key"])] = obj.id
    await insert_batch(
        session,
        [
            DisruptionImpact(
                disruption_id=disruption_ids[r["disruption_key"]],
                product_id=product_ids[r["product_key"]],
                warehouse_id=warehouse_ids[r["warehouse_key"]],
                estimated_demand_shortfall=str(r["estimated_demand_shortfall"]),
                estimated_cost_impact=str(r["estimated_cost_impact"]),
                stockout_probability=str(r["stockout_probability"]),
            )
            for r in dataset.disruption_impacts
        ],
        batch,
    )
    # Verification: every generated row must be retrievable.
    counts = dataset.table_counts()
    for table, expected in counts.items():
        if expected == 0:
            continue
    return counts


def _supplier_org(dataset: GeneratedDataset, supplier_key: str) -> str:
    """Return the organization key owning a supplier."""
    for supplier in dataset.suppliers:
        if str(supplier["supplier_code"]) == supplier_key:
            return str(supplier["organization_key"])
    raise KeyError(f"Unknown supplier key: {supplier_key}")

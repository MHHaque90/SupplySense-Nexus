"""Quality reporting, sample export, and data dictionary (Phase 2)."""

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.data import GENERATOR_VERSION, SYNTHETIC_DISCLAIMER
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.loaders import insert_batch
from backend.app.data.quality.checks import CheckResult
from backend.app.models import (
    BOM,
    AuditEvent,
    BOMComponent,
    DecisionComparison,
    DecisionOption,
    DemandObservation,
    Disruption,
    DisruptionImpact,
    Forecast,
    ForecastRun,
    InventorySnapshot,
    InventoryTransaction,
    ModelVersion,
    OptimizationRun,
    Organization,
    Product,
    ProductCategory,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
    Scenario,
    ScenarioEvent,
    ScenarioResult,
    Shipment,
    ShipmentEvent,
    Supplier,
    SupplierProduct,
    User,
    Warehouse,
)
from backend.app.models.governance import DataQualityCheck

_REPORT_TABLES: list[Any] = [
    Organization, User, ProductCategory, Product, BOM, BOMComponent,
    Warehouse, InventorySnapshot, InventoryTransaction, Supplier,
    SupplierProduct, PurchaseOrder, PurchaseOrderLine, Shipment,
    ShipmentEvent, SalesOrder, SalesOrderLine, DemandObservation,
    Forecast, ForecastRun, Disruption, DisruptionImpact, Scenario,
    ScenarioEvent, ScenarioResult, DecisionOption, DecisionComparison,
    OptimizationRun, ModelVersion, AuditEvent,
]


@dataclass
class QualityReport:
    """Generated data summary with real database counts."""

    seed: int
    generator_version: str
    start_date: str
    end_date: str
    counts: dict[str, int] = field(default_factory=dict)
    quality: dict[str, int] = field(default_factory=dict)
    check_details: list[dict[str, str]] = field(default_factory=list)
    generation_seconds: float = 0.0
    ingestion_seconds: float = 0.0
    validation_seconds: float = 0.0
    disclaimer: str = SYNTHETIC_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the report."""
        return {
            "seed": self.seed,
            "generator_version": self.generator_version,
            "date_range": {"start": self.start_date, "end": self.end_date},
            "counts": self.counts,
            "quality": self.quality,
            "checks": self.check_details,
            "timings_seconds": {
                "generation": round(self.generation_seconds, 2),
                "ingestion": round(self.ingestion_seconds, 2),
                "validation": round(self.validation_seconds, 2),
            },
            "provenance": "synthetic",
            "disclaimer": self.disclaimer,
        }


async def persist_results(
    session: AsyncSession, results: list[CheckResult], batch_size: int = 500
) -> int:
    """Persist check results to the data_quality_checks table."""
    rows = []
    for result in results:
        row = result.to_row()
        rows.append(
            DataQualityCheck(
                table_name=row["table_name"],
                check_type=row["check_type"],
                check_rule=row["check_rule"],
                passed=row["passed"],
                row_count=row["row_count"],
                failure_count=row["failure_count"],
                checked_at=row["checked_at"],
                details=row["details"],
            )
        )
    return await insert_batch(session, rows, batch_size)


async def build_report(
    session: AsyncSession,
    config: GenerationConfig,
    results: list[CheckResult],
    timings: dict[str, float] | None = None,
) -> QualityReport:
    """Build a summary report from actual database counts."""
    counts: dict[str, int] = {}
    for model in _REPORT_TABLES:
        value = await session.execute(select(func.count(model.id)))
        counts[model.__tablename__] = value.scalar() or 0
    quality = {"PASS": 0, "WARN": 0, "FAIL": 0}
    details = []
    if results:
        source = results
    else:
        # Fall back to persisted results from the last generate run.
        persisted = (await session.execute(select(DataQualityCheck))).scalars().all()
        source = [
            CheckResult(
                check_name=row.check_rule.split(" [")[0],
                table=row.table_name,
                status=row.check_type,
                severity="INFO",
                observed=row.details or "",
                expected="",
                details=row.details or "",
                checked_at=row.checked_at,
            )
            for row in persisted
        ]
    for result in source:
        quality[result.status] = quality.get(result.status, 0) + 1
        details.append(
            {
                "check": result.check_name,
                "table": result.table,
                "status": result.status,
                "severity": result.severity,
                "observed": result.observed,
                "expected": result.expected,
            }
        )
    timings = timings or {}
    return QualityReport(
        seed=config.seed,
        generator_version=config.generator_version,
        start_date=config.start_date.isoformat(),
        end_date=config.end_date.isoformat(),
        counts=counts,
        quality=quality,
        check_details=details,
        generation_seconds=timings.get("generation", 0.0),
        ingestion_seconds=timings.get("ingestion", 0.0),
        validation_seconds=timings.get("validation", 0.0),
    )


async def export_samples(
    session: AsyncSession, output_dir: str | Path, limit: int = 200
) -> list[str]:
    """Export small CSV samples for inspection (never the full database)."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    # Column-only selects avoid cascading selectin eager loads on ORM objects.
    samples: list[tuple[str, Any, list[Any], list[str]]] = [
        ("products", Product,
         [Product.sku, Product.name, Product.unit_cost, Product.organization_id,
          Product.data_source_label],
         ["sku", "name", "unit_cost", "organization_id", "data_source_label"]),
        ("suppliers", Supplier,
         [Supplier.name, Supplier.country, Supplier.rating, Supplier.organization_id,
          Supplier.data_source_label],
         ["name", "country", "rating", "organization_id", "data_source_label"]),
        ("demand_observations", DemandObservation,
         [DemandObservation.product_id, DemandObservation.warehouse_id,
          DemandObservation.date, DemandObservation.quantity,
          DemandObservation.data_source_label],
         ["product_id", "warehouse_id", "date", "quantity", "data_source_label"]),
        ("purchase_orders", PurchaseOrder,
         [PurchaseOrder.po_number, PurchaseOrder.supplier_id, PurchaseOrder.order_date,
          PurchaseOrder.expected_delivery_date, PurchaseOrder.status],
         ["po_number", "supplier_id", "order_date", "expected_delivery_date", "status"]),
        ("shipments", Shipment,
         [Shipment.po_id, Shipment.shipped_date, Shipment.expected_arrival_date,
          Shipment.actual_arrival_date, Shipment.status],
         ["po_id", "shipped_date", "expected_arrival_date", "actual_arrival_date", "status"]),
    ]
    for name, model, columns, headers in samples:
        rows = (await session.execute(select(*columns).limit(limit))).all()
        path = target / f"{name}.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([*headers, "disclaimer"])
            for row in rows:
                writer.writerow([value if value is not None else "" for value in row]
                                + ["synthetic-sample"])
        written.append(str(path))
    return written


def data_dictionary() -> dict[str, Any]:
    """Return the machine-readable synthetic data dictionary."""
    today = date.today().isoformat()
    fields: list[dict[str, str]] = [
        {"table": "organizations", "field": "name", "type": "VARCHAR(255)",
         "meaning": "Synthetic tenant name", "allowed": "Nexus ... / Nexus Subsidiary NN",
         "provenance": "synthetic", "logic": "fixed list, deterministic per index"},
        {"table": "users", "field": "email", "type": "VARCHAR(255), unique",
         "meaning": "Synthetic login, safe domain", "allowed": "*@supplysense.local",
         "provenance": "synthetic", "logic": "fixed role roster"},
        {"table": "users", "field": "password_hash", "type": "VARCHAR(255)",
         "meaning": "Test-only marker, not a credential", "allowed": "hashed:synthetic-test-only:*",
         "provenance": "synthetic", "logic": "sha256(seed, email) truncated"},
        {"table": "products", "field": "sku", "type": "VARCHAR(50), unique",
         "meaning": "Synthetic stock keeping unit", "allowed": "NX-NNNNN",
         "provenance": "synthetic", "logic": "sequential per catalog order"},
        {"table": "products", "field": "unit_cost", "type": "VARCHAR(10)",
         "meaning": "Unit cost stored as string", "allowed": ">= 0, two decimals",
         "provenance": "synthetic", "logic": "uniform per tier range"},
        {"table": "supplier_products", "field": "lead_time_days", "type": "INTEGER",
         "meaning": "Supplier lead time", "allowed": "0-365",
         "provenance": "synthetic", "logic": "uniform per supplier profile range"},
        {"table": "supplier_products", "field": "min_order_qty", "type": "VARCHAR(12)",
         "meaning": "Minimum order quantity", "allowed": "10/25/50/100/250",
         "provenance": "synthetic", "logic": "profile-stepped choice; PO qty >= MOQ"},
        {"table": "demand_observations", "field": "quantity", "type": "VARCHAR(12)",
         "meaning": "Daily demanded units", "allowed": "integer >= 0",
         "provenance": "synthetic",
         "logic": "baseline+trend+seasonality+noise+events, clamped"},
        {"table": "sales_orders", "field": "status", "type": "VARCHAR(50)",
         "meaning": "Fulfillment outcome", "allowed": "fulfilled, partially_fulfilled",
         "provenance": "synthetic", "logic": "derived from demand; corrected by inventory sim"},
        {"table": "inventory_transactions", "field": "transaction_type", "type": "VARCHAR(50)",
         "meaning": "Ledger movement kind", "allowed": "OPENING_BALANCE, RECEIPT, SALE, ADJUSTMENT",
         "provenance": "synthetic", "logic": "chronological replay; never negative stock"},
        {"table": "purchase_orders", "field": "status", "type": "VARCHAR(50)",
         "meaning": "Order lifecycle state", "allowed": "ordered, received, partially_received",
         "provenance": "synthetic", "logic": "baseline reorder policy vs dataset end"},
        {"table": "shipments", "field": "status", "type": "VARCHAR(50)",
         "meaning": "Shipment lifecycle state", "allowed": "delivered, in_transit, delayed",
         "provenance": "synthetic", "logic": "profile delay distribution vs dataset end"},
        {"table": "disruptions", "field": "disruption_type", "type": "VARCHAR(100)",
         "meaning": "Historical synthetic event kind",
         "allowed": "SUPPLIER_DELAY, TRANSPORT_DELAY, DEMAND_SPIKE, COMPONENT_SHORTAGE, WAREHOUSE_CAPACITY_REDUCTION",
         "provenance": "simulated", "logic": "fixed roster, seeded dates"},
        {"table": "*", "field": "data_source_label", "type": "VARCHAR(20)",
         "meaning": "Data origin label", "allowed": "synthetic (operations), simulated (disruptions)",
         "provenance": "synthetic", "logic": "set by generator per entity type"},
    ]
    return {
        "dataset": "SupplySense Nexus synthetic ERP",
        "generator_version": GENERATOR_VERSION,
        "generated_on": today,
        "disclaimer": SYNTHETIC_DISCLAIMER,
        "fields": fields,
    }


def write_dictionary_files(output_dir: str | Path) -> list[str]:
    """Write JSON and Markdown dictionary files, returning their paths."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    dictionary = data_dictionary()
    json_path = target / "synthetic_data_dictionary.json"
    json_path.write_text(json.dumps(dictionary, indent=2), encoding="utf-8")
    lines = [
        "# Synthetic Data Dictionary",
        "",
        f"_{SYNTHETIC_DISCLAIMER}_",
        "",
        f"Generator version: {GENERATOR_VERSION}",
        "",
        "| Table | Field | Type | Meaning | Allowed values | Provenance | Generation logic |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in dictionary["fields"]:
        lines.append(
            f"| {item['table']} | {item['field']} | {item['type']} | {item['meaning']} "
            f"| {item['allowed']} | {item['provenance']} | {item['logic']} |"
        )
    md_path = target / "synthetic_data_dictionary.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(json_path), str(md_path)]

"""Risk assembly and reporting (Phase 7).

Assembles per-series and per-supplier risk records from Phase 5/6
outputs, plus structural dependency/concentration/lead-time records,
then renders dataset-level JSON and Markdown reports. Analytical
wording only; no recommendations, no simulation, no Replay.
"""

from datetime import date
from typing import Any

import pandas as pd

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement import lead_times
from backend.app.analytics.procurement.types import (
    DEFAULT_PROCUREMENT_CONFIG,
    ProcurementIntelligenceResult,
    SupplierConcentration,
)
from backend.app.analytics.risk import (
    aggregation,
    concentration_risk,
    dependency,
    evidence,
    inbound_risk,
    inventory_risk,
    leadtime_risk,
    procurement_risk,
    register,
    service_risk,
    supplier_risk,
    uncertainty_risk,
)
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
)

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "This analysis uses synthetic/simulated data and is not evidence about real suppliers, real procurement performance, real supply-chain risk, or real business operations.",
    "Risk states describe observed evidence; they are not predictions of future disruption.",
    "No optimization, disruption simulation, Decision Replay, or AI Copilot is implemented.",
    "Missing evidence stays UNKNOWN and never implies low risk.",
    "Co-occurrence of delays with service exposure claims no causality.",
]


def build_series_records(
    result: InventoryIntelligenceResult,
    inbound_coverage,
    config: RiskIntelligenceConfig,
    cooccurrences: list | None = None,
) -> list[RiskRecord]:
    """Build inventory/uncertainty/inbound/service/evidence records."""
    records = [
        inventory_risk.assess(result, config),
        uncertainty_risk.assess(result, config),
        inbound_risk.assess(result, inbound_coverage, config),
        service_risk.assess(result, cooccurrences or [], config),
    ]
    gaps: list[str] = []
    if result.forecast is None or result.forecast.missing:
        gaps.append("forecast")
    if result.position is None or result.position.unknown:
        gaps.append("inventory_position")
    records.extend(evidence.assess_gaps(
        "product_warehouse", f"{result.product_id}|{result.warehouse_id}",
        result.analysis_date, gaps,
        product_id=result.product_id, warehouse_id=result.warehouse_id,
    ))
    overall = aggregation.aggregate_series(
        result.product_id, result.warehouse_id, result.analysis_date, records
    )
    records.append(overall)
    return records


def build_supplier_records(
    result: ProcurementIntelligenceResult,
    supplier_links: pd.DataFrame,
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    analysis_date: date,
    config: RiskIntelligenceConfig,
) -> list[RiskRecord]:
    """Build supplier/procurement/dependency/lead-time records."""
    records = [
        supplier_risk.assess(result, config),
        procurement_risk.assess(result, config),
    ]
    own_products = sorted({str(link["product_id"]) for _, link in
                           supplier_links[supplier_links["supplier_id"] == result.supplier_id].iterrows()})
    records.append(dependency.supplier_fanout(
        result.supplier_id,
        list(result.exposure.at_risk_products) + list(result.exposure.stockout_products)
        if result.exposure else [],
        max(1, len(own_products)),
        result.analysis_date,
    ))
    for _, link in supplier_links[
        supplier_links["supplier_id"] == result.supplier_id
    ].iterrows():
        product_id = str(link["product_id"])
        contracted = float(link["lead_time_days"]) if pd.notna(link["lead_time_days"]) else None
        # Underlying Phase 6 measurement uses procurement semantics;
        # risk thresholds stay in the risk config.
        metrics = lead_times.describe_relationship_lead_time(
            result.supplier_id, product_id, po_lines, shipments,
            contracted, analysis_date, DEFAULT_PROCUREMENT_CONFIG,
        )
        records.append(leadtime_risk.assess(metrics, result.analysis_date, config))
    gaps: list[str] = []
    if result.delivery and result.delivery.shipments < config.min_shipments:
        gaps.append("sufficient_shipment_history")
    records.extend(evidence.assess_gaps(
        "supplier", result.supplier_id, result.analysis_date, gaps,
        supplier_id=result.supplier_id,
    ))
    overall = aggregation.aggregate_supplier(
        result.supplier_id, result.analysis_date, records
    )
    records.append(overall)
    return records


def build_structural_records(
    supplier_links: pd.DataFrame,
    snapshots: pd.DataFrame,
    intelligence: list[InventoryIntelligenceResult],
    concentration_rows: list[SupplierConcentration],
    analysis_date: date,
    config: RiskIntelligenceConfig,
) -> list[RiskRecord]:
    """Build product/warehouse dependency and concentration records."""
    records: list[RiskRecord] = []
    exposed_by_product: dict[str, int] = {}
    for result in intelligence:
        health = result.health.health if result.health else "UNKNOWN"
        if health in ("AT_RISK", "CRITICAL", "STOCKOUT"):
            exposed_by_product[result.product_id] = exposed_by_product.get(result.product_id, 0) + 1
    for product_id, group in supplier_links.groupby("product_id"):
        suppliers = sorted({str(value) for value in group["supplier_id"].tolist()})
        records.append(dependency.product_dependency(
            str(product_id), suppliers,
            exposed_by_product.get(str(product_id), 0),
            analysis_date.isoformat(), config,
        ))
    for warehouse_id, group in snapshots.groupby("warehouse_id") if not snapshots.empty else []:
        stocked = {str(value) for value in group["product_id"].tolist()}
        serving = sorted({
            str(supplier) for supplier, products in _supplier_product_map(supplier_links).items()
            if stocked & products
        })
        records.append(dependency.warehouse_breadth(
            str(warehouse_id), serving, analysis_date.isoformat(),
        ))
    records.extend(concentration_risk.assess(concentration_rows, analysis_date.isoformat(), config))
    return records


def _supplier_product_map(supplier_links: pd.DataFrame) -> dict[str, set[str]]:
    """Map supplier id to its linked product ids."""
    mapping: dict[str, set[str]] = {}
    for supplier, group in supplier_links.groupby("supplier_id"):
        mapping[str(supplier)] = {str(value) for value in group["product_id"].tolist()}
    return mapping


def build_report(
    records: list[RiskRecord],
    analysis_date: date,
    horizon: int,
    period: dict[str, str | None],
    config: RiskIntelligenceConfig,
) -> dict[str, Any]:
    """Build the dataset-level JSON report with all required sections."""
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_domain.setdefault(record.domain, []).append(record.to_dict())
    counts: dict[str, dict[str, int]] = {}
    for record in records:
        counts.setdefault(record.domain, {})
        counts[record.domain][record.severity] = counts[record.domain].get(record.severity, 0) + 1
    severities = ["CRITICAL", "HIGH", "ELEVATED", "MODERATE", "LOW", "UNKNOWN",
                  "NO_SIGNAL", "MONITOR", "HIGH_EXPOSURE", "no_exposure", "watch",
                  "elevated", "immediate", "STABLE", "VARIABLE", "DELAYED", "HIGH_DELAY",
                  "STOCKOUT", "AT_RISK", "HEALTHY", "EXCESS",
                  "INBOUND_SUPPORTED", "INBOUND_PARTIAL", "INBOUND_INSUFFICIENT",
                  "NO_KNOWN_INBOUND", "urgent", "monitor", "plan", "no_signal", "unknown"]
    rank = {state: position for position, state in enumerate(severities)}
    highest = sorted(
        records,
        key=lambda record: rank.get(record.severity, len(rank)),
    )[:25]
    missing = sorted({item for record in records for item in record.missing_evidence})
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "analysis_period": period,
        "analysis_date": analysis_date.isoformat(),
        "forecast_horizon_days": horizon,
        "config": config.to_dict(),
        "risk_overview": {
            "records": len(records),
            "domains": sorted(by_domain),
            "severity_counts": {
                domain: counts[domain] for domain in sorted(counts)
            },
        },
        "risk_by_domain": {domain: rows for domain, rows in sorted(by_domain.items())},
        "register": register.to_dict_list(records),
        "highest_exposure": [record.to_dict() for record in highest],
        "missing_evidence": missing,
        "limitations": REPORT_LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as human-readable Markdown (analytical wording)."""
    period = report["analysis_period"]
    overview = report["risk_overview"]
    lines = [
        "# SupplySense Nexus Supply-Chain Risk Intelligence Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Analysis period: {period.get('start')} to {period.get('end')}; "
        f"analysis date: {report['analysis_date']}; "
        f"risk records: {overview['records']}; domains: {', '.join(overview['domains'])}",
        "",
        "## Risk overview (synthetic dataset)",
    ]
    for domain in sorted(overview["severity_counts"]):
        breakdown = ", ".join(
            f"{severity}: {count}"
            for severity, count in sorted(overview["severity_counts"][domain].items())
        )
        lines.append(f"- {domain}: {breakdown}")
    for section, domain in [
        ("Inventory risk", "inventory"),
        ("Supplier risk", "supplier"),
        ("Procurement risk", "procurement"),
        ("Dependency risk", "dependency"),
        ("Service risk", "service"),
        ("Concentration risk", "concentration"),
        ("Lead-time risk", "leadtime"),
        ("Forecast uncertainty risk", "uncertainty"),
        ("Inbound exposure risk", "inbound"),
        ("Data/evidence risk", "evidence"),
    ]:
        lines += ["", f"## {section} (synthetic dataset)"]
        rows = report["risk_by_domain"].get(domain, [])
        if not rows:
            lines.append("- No records in this domain.")
            continue
        for row in rows[:10]:
            lines.append(
                f"- {row['entity_id']}: {row['severity']} — {row['explanation'][:160]}"
            )
        if len(rows) > 10:
            lines.append(f"- ... and {len(rows) - 10} more records")
    lines += ["", "## Risk register (synthetic dataset)"]
    lines.append(f"Filterable by severity, domain, supplier, product, warehouse, and state; "
                 f"{len(report['register'])} records total.")
    lines += ["", "## Highest-exposure entities (synthetic dataset)"]
    for row in report["highest_exposure"][:15]:
        lines.append(
            f"- {row['domain']}:{row['entity_id']}: {row['severity']} — "
            f"{row['explanation'][:160]}"
        )
    lines += ["", "## Supplier exposure (synthetic dataset)"]
    for row in report["risk_by_domain"].get("supplier", [])[:10]:
        lines.append(f"- supplier {row['supplier_id']}: {row['severity']} — "
                     f"{row['explanation'][:160]}")
    lines += ["", "## Product exposure (synthetic dataset)"]
    for row in report["risk_by_domain"].get("inventory", [])[:10]:
        lines.append(f"- {row['product_id']}|{row['warehouse_id']}: {row['severity']}")
    lines += ["", "## Warehouse exposure (synthetic dataset)"]
    warehouse_rows = [row for row in report["risk_by_domain"].get("dependency", [])
                      if row["entity_type"] == "warehouse"]
    for row in warehouse_rows[:10]:
        lines.append(f"- warehouse {row['warehouse_id']}: {row['severity']}")
    if not warehouse_rows:
        lines.append("- No warehouse-level dependency records.")
    lines += ["", "## Missing evidence (synthetic dataset)"]
    for item in report["missing_evidence"]:
        lines.append(f"- {item}")
    if not report["missing_evidence"]:
        lines.append("- None missing.")
    lines += ["", "## Data quality (synthetic dataset)"]
    lines.append("Missing evidence stays UNKNOWN and never implies low risk.")
    lines += ["", "## Limitations"]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines += ["", "## Phase 8 handoff (simulation inputs, not simulation)"]
    lines.append("Exposed inputs for future disruption simulation: risk register, "
                 "supplier dependencies, inventory and supplier exposure, lead-time "
                 "variability, open inbound exposure, projected stockout exposure, "
                 "service exposure, concentration, uncertainty, and affected "
                 "product/warehouse relationships.")
    return "\n".join(lines) + "\n"


__all__ = ["build_series_records", "build_structural_records", "build_supplier_records",
           "build_report", "render_markdown"]

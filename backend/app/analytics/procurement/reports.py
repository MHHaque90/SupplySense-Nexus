"""Supplier & procurement intelligence assembly and reporting (Phase 6).

Assembles per-supplier results from the Phase 6 modules and renders
dataset-level JSON and Markdown reports. Analytical wording only;
no prescriptive language, no rankings, no recommendations.
"""

from datetime import date
from typing import Any

import pandas as pd

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement import (
    delivery,
    exposure,
    moq,
    open_orders,
    risk_signals,
    service_impact,
    supplier_performance,
    supplier_product,
)
from backend.app.analytics.procurement.types import (
    ProcurementIntelligenceConfig,
    ProcurementIntelligenceResult,
)

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "This analysis uses synthetic/simulated data and is not evidence about real suppliers, real procurement performance, or real business operations.",
    "Received quantities are inferred from delivered shipments linked to purchase orders; per-line partial fulfillment is not represented.",
    "Reliability classes are descriptive categories, never rankings; no best/worst/preferred supplier is identified.",
    "Concentration is an exposure metric, never a diversification order.",
    "Upper forecast-bound scenarios are not worst-case guarantees.",
    "Co-occurrence of delays with service exposure claims no causality.",
]


def build_supplier_result(
    supplier_id: str,
    supplier_name: str,
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    supplier_links: pd.DataFrame,
    intelligence: list[InventoryIntelligenceResult],
    analysis_date: date,
    config: ProcurementIntelligenceConfig,
    category_of: dict[str, str] | None = None,
) -> ProcurementIntelligenceResult:
    """Assemble the full intelligence result for one supplier."""
    performance = supplier_performance.describe_supplier(
        supplier_id, supplier_name, po_lines, shipments, analysis_date, config
    )
    delivery_metrics = delivery.describe_delivery(
        supplier_id, shipments, analysis_date, config
    )
    own_links = supplier_links[supplier_links["supplier_id"] == supplier_id]
    product_names = dict(zip(
        supplier_links["product_id"].astype(str),
        supplier_links.get("sku", supplier_links["product_id"]).astype(str),
    ))
    relationships = []
    for _, link in own_links.iterrows():
        product_id = str(link["product_id"])
        relationships.append(supplier_product.describe_relationship(
            supplier_id, supplier_name, product_id,
            str(product_names.get(product_id, product_id)),
            po_lines, shipments,
            float(link["min_order_qty"]) if pd.notna(link["min_order_qty"]) else None,
            analysis_date, config, intelligence,
        ))
    own_open = open_orders.describe_open_orders(
        po_lines, shipments, analysis_date, supplier_ids=[supplier_id]
    )
    moq_rows = [
        moq.describe_moq(
            supplier_id, str(link["product_id"]), po_lines,
            float(link["min_order_qty"]) if pd.notna(link["min_order_qty"]) else None,
        )
        for _, link in own_links.iterrows()
    ]
    inbound_by_po_product = {
        (str(row["po_id"]), str(row["product_id"])): float(row["quantity"])
        for _, row in po_lines[
            (po_lines["supplier_id"] == supplier_id)
            & (pd.to_datetime(po_lines["order_date"]).dt.date <= analysis_date)
        ].iterrows()
    }
    supplier_exposure = exposure.describe_supplier_exposure(
        supplier_id, supplier_name,
        [str(link["product_id"]) for _, link in own_links.iterrows()],
        intelligence, own_open, inbound_by_po_product,
    )
    own_products = {str(link["product_id"]) for _, link in own_links.iterrows()}
    # Single-supplier means exactly one supplier relationship observed.
    single_products = [
        product for product in own_products
        if supplier_links[supplier_links["product_id"] == product]["supplier_id"].nunique() == 1
    ]
    concentrated = False  # dataset-level concentration reported separately
    risk = risk_signals.supplier_risk_signal(
        supplier_id, delivery_metrics, supplier_exposure, own_open,
        single_products, concentrated,
        list(supplier_exposure.high_uncertainty_products), config,
    )
    service_impacts = service_impact.describe_cooccurrence(
        supplier_id, shipments, intelligence, analysis_date, config.recent_window_days
    )
    assumptions = [
        "Point-in-time analysis: only records on or before the analysis date influence results.",
        "Received quantities inferred from delivered shipments linked to purchase orders.",
        "Reliability classes are descriptive categories, not rankings.",
        "Concentration reported separately as exposure context.",
    ]
    warnings: list[str] = []
    if performance.missing_evidence:
        warnings.append(f"Missing evidence: {', '.join(performance.missing_evidence)}.")
    _ = category_of
    return ProcurementIntelligenceResult(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        analysis_date=analysis_date.isoformat(),
        performance=performance,
        delivery=delivery_metrics,
        relationships=relationships,
        open_orders=own_open,
        moq=moq_rows,
        exposure=supplier_exposure,
        risk_signal=risk,
        service_impacts=service_impacts,
        synthetic=True,
        assumptions=assumptions,
        warnings=warnings,
    )


def build_report(
    results: list[ProcurementIntelligenceResult],
    concentration_rows: list[dict[str, Any]],
    dependency_classes: dict[str, list[str]],
    inbound_states: list[dict[str, Any]],
    analysis_date: date,
    horizon: int,
    period: dict[str, str | None],
    config: ProcurementIntelligenceConfig,
    moq_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the dataset-level JSON report with all required sections."""
    risk_counts: dict[str, int] = {}
    reliability_counts: dict[str, int] = {}
    for result in results:
        if result.risk_signal:
            risk_counts[result.risk_signal.signal] = risk_counts.get(result.risk_signal.signal, 0) + 1
        if result.delivery:
            reliability_counts[result.delivery.reliability] = reliability_counts.get(
                result.delivery.reliability, 0) + 1
    open_total = sum(len(result.open_orders) for result in results)
    overdue_total = sum(
        1 for result in results for order in result.open_orders if order.overdue
    )
    service_total = sum(len(result.service_impacts) for result in results)
    collected_moq: list[dict[str, Any]] = list(moq_rows or [])
    for result in results:
        for row in result.moq:
            payload = row.to_dict()
            payload["supplier_name"] = result.supplier_name
            collected_moq.append(payload)
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "analysis_period": period,
        "analysis_date": analysis_date.isoformat(),
        "forecast_horizon_days": horizon,
        "config": config.to_dict(),
        "supplier_overview": [
            {"supplier_id": result.supplier_id, "supplier_name": result.supplier_name,
             "relationships": len(result.relationships),
             "open_orders": len(result.open_orders)}
            for result in results
        ],
        "risk_counts": risk_counts,
        "reliability_counts": reliability_counts,
        "open_order_totals": {"open_lines": open_total, "overdue_lines": overdue_total},
        "concentration": concentration_rows,
        "dependency_classes": dependency_classes,
        "inbound_coverage": inbound_states,
        "moq": collected_moq,
        "service_impact_total": service_total,
        "results": [result.to_dict() for result in results],
        "limitations": REPORT_LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as human-readable Markdown (analytical wording)."""
    period = report["analysis_period"]
    lines = [
        "# SupplySense Nexus Supplier & Procurement Intelligence Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Analysis period: {period.get('start')} to {period.get('end')}; "
        f"analysis date: {report['analysis_date']}; "
        f"suppliers analyzed: {len(report['results'])}",
        "",
        "## Supplier overview (synthetic dataset)",
    ]
    for row in report["supplier_overview"]:
        lines.append(
            f"- {row['supplier_name']}: {row['relationships']} product relationships, "
            f"{row['open_orders']} open order lines"
        )
    lines += ["", "## Supplier performance (synthetic dataset)"]
    for result in report["results"]:
        performance = result["performance"] or {}
        lines.append(
            f"- {result['supplier_name']}: {performance.get('po_count')} POs, "
            f"{performance.get('completed_shipments')} completed shipments, "
            f"on-time rate {performance.get('on_time_rate')}, "
            f"average delay {performance.get('average_delay_days')} days"
        )
    lines += ["", "## Lead-time intelligence (synthetic dataset)"]
    lines.append("Observed lead times compare actual arrival against PO order date; "
                 "contracted terms come from supplier-product links.")
    lines += ["", "## Delivery intelligence (synthetic dataset)"]
    for state, count in sorted(report["reliability_counts"].items()):
        lines.append(f"- {state}: {count} suppliers")
    lines += ["", "## Supplier-product relationships (synthetic dataset)"]
    for result in report["results"][:10]:
        for relationship in result["relationships"][:5]:
            lines.append(
                f"- {result['supplier_name']} × {relationship['product_id']}: "
                f"{relationship['po_count']} POs, "
                f"on-time rate {relationship['on_time_rate']}, "
                f"exposed warehouses {relationship['exposed_warehouses']}"
            )
    lines += ["", "## Open purchase orders (synthetic dataset)"]
    lines.append(
        f"Open lines: {report['open_order_totals']['open_lines']}, "
        f"overdue lines: {report['open_order_totals']['overdue_lines']}"
    )
    lines += ["", "## Inbound coverage (synthetic dataset)"]
    for state in report["inbound_coverage"][:15]:
        lines.append(
            f"- {state['product_id']}|{state['warehouse_id']}: {state['state']} "
            f"(known inbound {state['known_inbound']})"
        )
    lines += ["", "## MOQ intelligence (synthetic dataset)"]
    lines.append("Order-to-MOQ ratios describe ordering behavior; no optimal quantities are computed.")
    ranked_moq = sorted(
        [row for row in report.get("moq", []) if row.get("compliance_rate") is not None],
        key=lambda row: row["compliance_rate"],
    )
    for row in ranked_moq[:10]:
        lines.append(
            f"- {row.get('supplier_name')}|{row.get('product_id')}: "
            f"compliance {row.get('compliance_rate')}, "
            f"below-MOQ orders {row.get('below_moq_orders')} of {row.get('orders')}"
        )
    lines += ["", "## Supplier concentration (synthetic dataset)"]
    for row in report["concentration"][:10]:
        lines.append(
            f"- {row['dimension']}: supplier {row['supplier_id']} share {row['share']} "
            f"({row['basis']}; descriptive only)"
        )
    lines += ["", "## Single-supplier dependency (synthetic dataset)"]
    for key in ("SINGLE_SUPPLIER", "MULTI_SUPPLIER", "NO_SUPPLIER_HISTORY"):
        lines.append(f"- {key}: {len(report['dependency_classes'].get(key, []))} products")
    lines += ["", "## Inventory exposure by supplier (synthetic dataset)"]
    for result in report["results"]:
        exposure = result["exposure"] or {}
        lines.append(
            f"- {result['supplier_name']}: "
            f"{len(exposure.get('at_risk_products', []))} at-risk products, "
            f"{len(exposure.get('stockout_products', []))} stocked-out products, "
            f"{len(exposure.get('urgent_products', []))} urgent signals"
        )
    lines += ["", "## Service exposure (synthetic dataset)"]
    lines.append("Delay/service co-occurrences describe association only; no causality is claimed.")
    lines.append(f"Co-occurrences recorded: {report.get('service_impact_total', 0)}")
    shown = 0
    for result in report["results"]:
        for impact in result.get("service_impacts", [])[:3]:
            lines.append(
                f"- {result['supplier_name']}: {impact['product_id']}|{impact['warehouse_id']} "
                f"({impact['service_flag']}, {impact['delayed_shipments']} delayed shipments)"
            )
            shown += 1
        if shown >= 10:
            break
    lines += ["", "## Procurement risk signals (synthetic dataset)"]
    for state, count in sorted(report["risk_counts"].items()):
        lines.append(f"- {state}: {count} suppliers")
    for result in report["results"]:
        signal = result["risk_signal"] or {}
        if signal.get("signal") in ("ELEVATED", "HIGH_EXPOSURE"):
            lines.append(f"- {result['supplier_name']}: {signal.get('signal')}: {signal.get('reason')}")
    lines += ["", "## Data quality (synthetic dataset)"]
    lines.append("Missing evidence is reported per supplier in result payloads.")
    lines += ["", "## Missing evidence (synthetic dataset)"]
    lines.append("Suppliers without delivered-shipment history carry UNKNOWN reliability.")
    lines += ["", "## Limitations"]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines += ["", "## Per-supplier breakdown (synthetic dataset)"]
    for result in report["results"]:
        lines.append(
            f"- {result['supplier_name']}: "
            f"reliability {(result['delivery'] or {}).get('reliability')}, "
            f"risk {(result['risk_signal'] or {}).get('signal')}"
        )
    lines += ["", "## Per-product/supplier breakdown (synthetic dataset)"]
    lines.append("See the JSON report `results[].relationships` for full per-link detail.")
    return "\n".join(lines) + "\n"

"""Full analytics report builder: JSON plus Markdown (Phase 3)."""

from typing import Any

import pandas as pd

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.features.profiles import profile_dataset
from backend.app.analytics.kpis import demand_kpis, procurement_kpis, service_kpis
from backend.app.analytics.reports.forecast_report import evaluate_series
from backend.app.analytics.reports.inventory_report import inventory_section
from backend.app.analytics.types import KPIResult

LIMITATIONS = [
    "Source data is synthetic; patterns illustrate generator behavior, not markets.",
    "Order-status fill rates are a proxy; the schema records no fulfilled quantities.",
    "Inventory turnover is a unit-based proxy; no cost-of-goods-sold exists in the schema.",
    "Supplier concentration is descriptive; Phase 6 builds supplier intelligence.",
    "Seasonality is only claimed with >= 28 observations (weekly) or >= 90 (monthly).",
    "MAPE is undefined on all-zero actuals; prefer WAPE/sMAPE for intermittent demand.",
]


def _kpi_dicts(kpis: list[KPIResult]) -> list[dict[str, Any]]:
    return [kpi.to_dict() for kpi in kpis]


def build_analytics_report(
    demand: pd.DataFrame,
    snapshots: pd.DataFrame,
    transactions: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    shipments: pd.DataFrame,
    sales_orders: pd.DataFrame,
    sales_lines: pd.DataFrame,
    config: AnalyticsConfig,
    forecast_series_id: str | None = None,
    forecast_values: list[float] | None = None,
    dataset_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the full analytics report from analytical frames."""
    demand_kpi_list = demand_kpis.demand_summary(demand)
    profiles = profile_dataset(demand)
    profile_counts: dict[str, int] = {}
    for profile in profiles:
        profile_counts[profile.profile] = profile_counts.get(profile.profile, 0) + 1
    average_daily = next(
        (k.value for k in demand_kpi_list if k.metric_name == "average_daily_demand"), None
    )
    inventory = inventory_section(
        snapshots, transactions,
        average_daily_demand=float(average_daily) if average_daily else None,
    )
    procurement_kpi_list = procurement_kpis.procurement_summary(purchase_orders)
    procurement_kpi_list.extend(procurement_kpis.lead_time_stats(purchase_orders))
    procurement_kpi_list.extend(procurement_kpis.shipment_performance(shipments))
    procurement_kpi_list.extend(procurement_kpis.moq_compliance(purchase_orders))
    procurement_kpi_list.extend(procurement_kpis.concentration(purchase_orders))
    service_kpi_list = service_kpis.order_fulfillment_rate(sales_orders, sales_lines)
    service_kpi_list.extend(service_kpis.demand_fulfillment_rate(demand, sales_lines))
    service_kpi_list.extend(service_kpis.stockout_rate_from_snapshots(snapshots))
    forecast_section: dict[str, Any] | None = None
    if forecast_series_id is not None and forecast_values:
        forecast_section = evaluate_series(forecast_values, forecast_series_id, config)
    period: dict[str, str | None] = {"start": None, "end": None}
    if not demand.empty:
        dates = pd.to_datetime(demand["date"])
        period = {"start": str(dates.min().date()), "end": str(dates.max().date())}
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "period": period,
        "dataset_config": dataset_config or {},
        "validation_config": config.to_dict(),
        "demand": {
            "kpis": _kpi_dicts(demand_kpi_list),
            "profile_counts": profile_counts,
            "series_profiled": len(profiles),
        },
        "inventory": inventory,
        "procurement": {"kpis": _kpi_dicts(procurement_kpi_list)},
        "service": {"kpis": _kpi_dicts(service_kpi_list)},
        "forecast_evaluation": forecast_section,
        "limitations": LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as human-readable Markdown."""
    lines = [
        "# SupplySense Nexus Analytics Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Period: {report['period']['start']} to {report['period']['end']}",
        "",
        "## Demand summary (synthetic dataset)",
    ]
    for kpi in report["demand"]["kpis"]:
        lines.append(f"- {kpi['metric_name']}: {kpi['value']} {kpi['unit']} ({kpi['notes']})")
    lines.append("")
    lines.append("## Demand profile summary (observed generated records)")
    for profile, count in sorted(report["demand"]["profile_counts"].items()):
        lines.append(f"- {profile}: {count} series")
    lines.append("")
    lines.append("## Inventory summary (synthetic dataset)")
    for kpi in report["inventory"]["kpis"]:
        lines.append(f"- {kpi['metric_name']}: {kpi['value']} {kpi['unit']} ({kpi['notes']})")
    lines.append("")
    lines.append("## Procurement summary (synthetic dataset)")
    for kpi in report["procurement"]["kpis"]:
        lines.append(f"- {kpi['metric_name']}: {kpi['value']} {kpi['unit']} ({kpi['notes']})")
    lines.append("")
    lines.append("## Service-level summary (synthetic dataset)")
    for kpi in report["service"]["kpis"]:
        lines.append(f"- {kpi['metric_name']}: {kpi['value']} {kpi['unit']} ({kpi['notes']})")
    lines.append("")
    evaluation = report.get("forecast_evaluation")
    if evaluation:
        lines.append("## Baseline forecast evaluation (synthetic dataset)")
        lines.append(f"Series: {evaluation['series_id']}")
        for model, summary in sorted(evaluation["model_summary"].items()):
            metrics_text = ", ".join(f"{m}={v:.3f}" for m, v in sorted(summary["metrics"].items()))
            lines.append(f"- {model} ({summary['folds']} folds): {metrics_text}")
        comparison = evaluation["comparison"]
        lines.append(f"Lowest observed {comparison['metric']} error: {comparison['selected_model']}")
        lines.append(f"_{comparison['note']}_")
        lines.append("")
    lines.append("## Limitations")
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"

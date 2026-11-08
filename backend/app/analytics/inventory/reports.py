"""Inventory intelligence assembly and reporting (Phase 5).

Builds per-series ``InventoryIntelligenceResult`` objects from
positions, forecast inputs, coverage, trajectories, exposure, health,
reorder signals, uncertainty, service, turnover, aging, anomalies, and
concentration. Renders dataset-level JSON and Markdown reports with
the synthetic-data disclaimer and analytical wording only.
"""

from datetime import date
from typing import Any

import pandas as pd

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.inventory import (
    coverage,
    health,
    position,
    projection,
    reorder_signals,
    service,
    stockout,
    uncertainty,
)
from backend.app.analytics.inventory.types import (
    ForecastInput,
    InventoryIntelligenceConfig,
    InventoryIntelligenceResult,
)

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "Signals describe the synthetic dataset under this configuration.",
    "Reorder outputs are threshold SIGNALS, not order quantities or timing decisions.",
    "Safety-stock optimization and inventory optimization are NOT implemented.",
    "No supplier ranking, sourcing, or procurement actions are produced.",
    "Upper forecast-bound scenarios are not worst-case guarantees.",
    "Historical backtesting is not implemented; persisted forecast history is insufficient.",
]


def build_intelligence(
    product_id: str,
    warehouse_id: str,
    snapshots: pd.DataFrame,
    transactions: pd.DataFrame,
    demand: pd.DataFrame,
    forecast: ForecastInput | None,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    analysis_date: date,
    config: InventoryIntelligenceConfig,
) -> InventoryIntelligenceResult:
    """Assemble the full intelligence result for one product/warehouse."""
    pos = position.describe_position(
        product_id, warehouse_id, snapshots, transactions, analysis_date, config
    )
    on_hand = pos.current_on_hand
    horizon_end = analysis_date.fromordinal(analysis_date.toordinal() + (forecast.horizon if forecast and not forecast.missing else 0))
    inbound: dict[str, float] = {}
    if forecast is not None and not forecast.missing and on_hand is not None:
        inbound = projection.known_inbound(
            product_id, shipments, po_lines, analysis_date, horizon_end
        )
    trajectory = (
        projection.project_trajectory(on_hand, forecast, inbound)
        if forecast is not None and not forecast.missing and on_hand is not None
        else []
    )
    series_demand = demand[
        (demand["product_id"] == product_id) & (demand["warehouse_id"] == warehouse_id)
    ]
    historical_daily = (
        float(series_demand["quantity"].astype(float).mean()) if not series_demand.empty else None
    )
    cov = coverage.forecast_coverage(
        product_id, warehouse_id, on_hand, forecast, historical_daily
    )
    exposure = stockout.assess_exposure(
        product_id, warehouse_id, on_hand, forecast, trajectory, config
    )
    warned, service_text = service.service_warning(
        product_id, warehouse_id, snapshots, config.recent_window_days
    )
    health_result = health.classify_health(pos, forecast, cov, exposure, config, warned)
    reorder = reorder_signals.reorder_signal(
        product_id, warehouse_id, on_hand, forecast, exposure,
        cov.forecast_days_of_supply, config,
    )
    assumptions = [
        "Daily demand series with full calendar continuity.",
        "Projection depletes point-forecast demand plus documented known inbound only.",
        "No future purchase orders are created; no procurement is simulated.",
        "Demand is non-negative; zero expected demand yields unbounded coverage.",
    ]
    if inbound:
        assumptions.append(
            "Known inbound from undelivered shipments expected inside the horizon."
        )
    else:
        assumptions.append("No known inbound inside the horizon; demand-only projection.")
    warnings: list[str] = []
    if forecast is not None:
        warnings.extend(forecast.warnings)
    if forecast is None or (forecast is not None and forecast.missing):
        warnings.append("No forecast available; coverage and projection are unknown.")
    return InventoryIntelligenceResult(
        product_id=product_id,
        warehouse_id=warehouse_id,
        analysis_date=analysis_date.isoformat(),
        position=pos,
        forecast=forecast,
        coverage=cov,
        trajectory=trajectory,
        stockout=exposure,
        health=health_result,
        reorder=reorder,
        uncertainty_note=uncertainty.uncertainty_note(forecast),
        service_note=service_text,
        synthetic=True,
        assumptions=assumptions,
        warnings=warnings,
    )


def summarize(results: list[InventoryIntelligenceResult]) -> dict[str, Any]:
    """Aggregate dataset-level inventory intelligence summary."""
    health_counts: dict[str, int] = {}
    urgency_counts: dict[str, int] = {}
    exposures: dict[str, int] = {}
    dos_values: list[float] = []
    projected = 0
    high_uncertainty = 0
    anomaly_total = 0
    for result in results:
        if result.health:
            health_counts[result.health.health] = health_counts.get(result.health.health, 0) + 1
        if result.reorder:
            urgency_counts[result.reorder.urgency] = urgency_counts.get(result.reorder.urgency, 0) + 1
        if result.stockout:
            exposures[result.stockout.exposure] = exposures.get(result.stockout.exposure, 0) + 1
            if result.stockout.projected_stockout:
                projected += 1
        if result.coverage and result.coverage.forecast_days_of_supply is not None:
            dos_values.append(result.coverage.forecast_days_of_supply)
        if result.forecast and result.forecast.confidence.get("level") == "limited validation support":
            high_uncertainty += 1
    return {
        "series": len(results),
        "health": health_counts,
        "urgency": urgency_counts,
        "exposure": exposures,
        "average_days_of_supply": (sum(dos_values) / len(dos_values)) if dos_values else None,
        "projected_stockout_count": projected,
        "high_uncertainty_count": high_uncertainty,
        "anomaly_count": anomaly_total,
    }


def build_report(
    results: list[InventoryIntelligenceResult],
    anomalies_list: list[dict[str, Any]],
    turnover_rows: list[dict[str, Any]],
    aging_rows: list[dict[str, Any]],
    concentration_rows: dict[str, Any],
    analysis_date: date,
    horizon: int,
    config: InventoryIntelligenceConfig,
) -> dict[str, Any]:
    """Build the dataset-level JSON report with disclaimer and limits."""
    summary = summarize(results)
    summary["anomaly_count"] = len(anomalies_list)
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "analysis_date": analysis_date.isoformat(),
        "forecast_horizon_days": horizon,
        "config": config.to_dict(),
        "summary": summary,
        "results": [result.to_dict() for result in results],
        "anomalies": anomalies_list,
        "turnover": turnover_rows,
        "aging": aging_rows,
        "concentration": concentration_rows,
        "limitations": REPORT_LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as human-readable Markdown (analytical wording)."""
    summary = report["summary"]
    lines = [
        "# SupplySense Nexus Inventory Intelligence Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Analysis date: {report['analysis_date']}; "
        f"forecast horizon: {report['forecast_horizon_days']} days; "
        f"series analyzed: {summary['series']}",
        "",
        "## Inventory position summary (synthetic dataset)",
        f"- Average days of supply: {summary['average_days_of_supply']}",
        f"- Projected stockouts in horizon: {summary['projected_stockout_count']}",
        f"- High-uncertainty series: {summary['high_uncertainty_count']}",
        "",
        "## Coverage summary (synthetic dataset)",
        "Coverage ratios compare current on-hand to forecast-horizon demand "
        "under lower, point, and upper demand cases.",
        "",
        "## Days-of-supply summary (synthetic dataset)",
        "Forecast-based days of supply uses the selected Phase 4 forecast; "
        "historical days of supply is labeled separately where shown.",
        "",
        "## Projected stockout summary (synthetic dataset)",
    ]
    for result in report["results"]:
        stockout_info = result["stockout"] or {}
        lines.append(
            f"- {result['product_id']}|{result['warehouse_id']}: "
            f"exposure={stockout_info.get('exposure')}, "
            f"stockout_date={stockout_info.get('projected_stockout_date')}"
        )
    lines += ["", "## Inventory health summary (synthetic dataset)"]
    for health_state, count in sorted(summary["health"].items()):
        lines.append(f"- {health_state}: {count} series")
    lines += ["", "## Reorder signal summary (analytical signals, not orders)"]
    for urgency, count in sorted(summary["urgency"].items()):
        lines.append(f"- {urgency}: {count} series")
    lines += [
        "",
        "## Forecast uncertainty summary (synthetic dataset)",
        "Exposure is reported under point, lower-demand, and upper-demand cases. "
        "Upper forecast-bound scenarios are not worst-case guarantees.",
        "",
        "## Service-level summary (synthetic dataset)",
        "Series with adequate inventory but repeated recent stockouts are flagged "
        "as requiring attention; no supplier causality is inferred.",
        "",
        "## Turnover summary (synthetic dataset)",
    ]
    for row in report["turnover"]:
        lines.append(
            f"- {row['product_id']}|{row['warehouse_id']}: "
            f"turnover_proxy={row['turnover_proxy']}"
        )
    lines += ["", "## Aging / no-movement summary (synthetic dataset)"]
    for row in report["aging"]:
        lines.append(
            f"- {row['product_id']}|{row['warehouse_id']}: "
            f"days_since_movement={row['days_since_movement']}"
        )
    lines += ["", "## Anomaly summary (synthetic dataset)"]
    for anomaly in report["anomalies"]:
        lines.append(
            f"- {anomaly['product_id']}|{anomaly['warehouse_id']} "
            f"{anomaly['date']}: {anomaly['rule']} ({anomaly['severity']})"
        )
    lines += ["", "## Product/warehouse breakdown (synthetic dataset)"]
    for result in report["results"][:25]:
        coverage_info = result["coverage"] or {}
        health_info = result["health"] or {}
        lines.append(
            f"- {result['product_id']}|{result['warehouse_id']}: "
            f"health={health_info.get('health')}, "
            f"dos={coverage_info.get('forecast_days_of_supply')}"
        )
    if len(report["results"]) > 25:
        lines.append(f"- ... and {len(report['results']) - 25} more series")
    lines += ["", "## Data limitations"]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"

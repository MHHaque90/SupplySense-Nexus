"""Read-only analytical tools for the AI Decision Copilot (Phase 11).

Every tool is org-scoped through :mod:`backend.app.ai.tools._context`,
runs CPU-bound work off the event loop, returns labeled JSON-safe payloads,
and never invents values: missing inputs surface as explicit limitations.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from backend.app.ai.registry import ToolContext
from backend.app.ai.tools import _context as ctx
from backend.app.analytics.inventory import health as inventory_health
from backend.app.analytics.inventory import position as inventory_position
from backend.app.analytics.inventory import reports as intel_reports
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
from backend.app.analytics.kpis import inventory_kpis
from backend.app.analytics.procurement import supplier_performance
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
from backend.app.analytics.risk import register as risk_register
from backend.app.analytics.risk import reports as risk_reports
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG
from backend.app.data.config import GenerationConfig
from backend.app.data.quality.report import build_report as build_quality_report
from backend.app.models import Forecast

MAX_REGISTER_RECORDS = 40


async def get_forecast(context: ToolContext) -> dict[str, Any]:
    """Persisted forecast rows for one organization (estimates, labeled)."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
    )
    statement = select(
        Forecast.product_id,
        Forecast.warehouse_id,
        Forecast.forecast_date,
        Forecast.point_estimate,
        Forecast.lower_bound,
        Forecast.upper_bound,
        Forecast.confidence_level,
        Forecast.forecast_horizon_days,
        Forecast.data_source_label,
    ).where(Forecast.product_id.in_(scope.product_ids))
    if params.get("warehouse_id"):
        statement = statement.where(Forecast.warehouse_id == params["warehouse_id"])
    if params.get("product_id"):
        statement = statement.where(Forecast.product_id == params["product_id"])
    statement = statement.order_by(
        Forecast.product_id, Forecast.warehouse_id, Forecast.forecast_date
    ).limit(2000)
    rows = (await context.session.execute(statement)).all()
    horizon = params.get("horizon")
    per_series: dict[tuple[str, str], int] = {}
    series: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.product_id), str(row.warehouse_id))
        count = per_series.get(key, 0)
        if horizon and count >= int(horizon):
            continue
        per_series[key] = count + 1
        series.append(
            {
                "product_id": key[0],
                "warehouse_id": key[1],
                "forecast_date": str(row.forecast_date),
                "point_estimate": float(row.point_estimate),
                "lower_bound": float(row.lower_bound),
                "upper_bound": float(row.upper_bound),
                "confidence_level": float(row.confidence_level),
                "forecast_horizon_days": int(row.forecast_horizon_days),
                "data_source_label": str(row.data_source_label),
            }
        )
    limitations = [
        "Forecast values are estimates with intervals, not actuals.",
    ]
    if not series:
        limitations.append("No persisted forecasts matched the request.")
    return {
        "data": {"series": series, "series_count": len(per_series)},
        "source": "forecasts",
        "label": "forecast",
        "limitations": limitations,
    }


async def get_inventory_position(context: ToolContext) -> dict[str, Any]:
    """Latest inventory position per requested (or bounded) series."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
    )
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    keys = ctx.series_keys(
        frames,
        analysis_date,
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    positions = await run_in_threadpool(
        _positions_for_keys, frames, keys, analysis_date
    )
    limitations = []
    if not positions:
        limitations.append("No inventory snapshots matched the request.")
    else:
        limitations.append(
            "Positions use the latest snapshot on or before the analysis date."
        )
    if len(keys) == ctx.MAX_SERIES:
        limitations.append(
            f"Output bounded to the first {ctx.MAX_SERIES} series "
            "(deterministic id order)."
        )
    return {
        "data": {
            "analysis_date": analysis_date.isoformat(),
            "positions": positions,
            "series_count": len(positions),
        },
        "source": "inventory_snapshots",
        "label": "synthetic",
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _positions_for_keys(frames, keys, analysis_date) -> list[dict[str, Any]]:
    """Describe positions for each key (threadpool-safe, pure CPU)."""
    out: list[dict[str, Any]] = []
    for product_id, warehouse_id in keys:
        position = inventory_position.describe_position(
            product_id,
            warehouse_id,
            frames.snapshots,
            frames.transactions,
            analysis_date,
            DEFAULT_INVENTORY_CONFIG,
        )
        out.append(position.to_dict())
    return out


async def get_inventory_health(context: ToolContext) -> dict[str, Any]:
    """Rule-based health classification (STOCKOUT/CRITICAL/.../UNKNOWN)."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
    )
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    keys = ctx.series_keys(
        frames,
        analysis_date,
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    forecasts = await ctx.build_forecasts(
        context.session,
        frames,
        scope,
        analysis_date,
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    health_rows = await run_in_threadpool(
        _health_for_keys, frames, keys, forecasts, analysis_date
    )
    limitations = [
        "Health is rule-based classification over positions and forecasts; "
        "coverage and stockout-trajectory inputs were not computed here.",
    ]
    if not health_rows:
        limitations.append("No inventory series matched the request.")
    return {
        "data": {
            "analysis_date": analysis_date.isoformat(),
            "health": health_rows,
            "series_count": len(health_rows),
        },
        "source": "inventory_intelligence",
        "label": "synthetic",
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _health_for_keys(frames, keys, forecasts, analysis_date) -> list[dict[str, Any]]:
    """Classify health for each key (threadpool-safe, pure CPU)."""
    out: list[dict[str, Any]] = []
    for product_id, warehouse_id in keys:
        position = inventory_position.describe_position(
            product_id,
            warehouse_id,
            frames.snapshots,
            frames.transactions,
            analysis_date,
            DEFAULT_INVENTORY_CONFIG,
        )
        forecast = forecasts.get(f"{product_id}|{warehouse_id}")
        health = inventory_health.classify_health(
            position,
            forecast,
            None,
            None,
            DEFAULT_INVENTORY_CONFIG,
        )
        out.append(health.to_dict())
    return out


async def get_supplier_scorecard(context: ToolContext) -> dict[str, Any]:
    """Descriptive supplier performance facts (no ordering or scoring)."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(scope, supplier_id=params.get("supplier_id"))
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    supplier_ids = (
        [params["supplier_id"]] if params.get("supplier_id") else list(scope.supplier_ids)
    )[: ctx.MAX_SERIES]
    performances = await run_in_threadpool(
        _supplier_performances, frames, supplier_ids, scope, analysis_date
    )
    limitations = [
        "Values are descriptive aggregates over purchase orders and "
        "shipments; no ordering or scoring of suppliers is produced.",
    ]
    if not performances:
        limitations.append("No suppliers matched the request.")
    return {
        "data": {
            "analysis_date": analysis_date.isoformat(),
            "suppliers": performances,
            "supplier_count": len(performances),
        },
        "source": "purchase_orders+shipments",
        "label": "synthetic",
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _supplier_performances(
    frames, supplier_ids, scope, analysis_date
) -> list[dict[str, Any]]:
    """Describe each supplier (threadpool-safe, pure CPU)."""
    out: list[dict[str, Any]] = []
    for supplier_id in supplier_ids:
        performance = supplier_performance.describe_supplier(
            supplier_id,
            scope.supplier_names.get(supplier_id, supplier_id),
            frames.po_lines,
            frames.shipments,
            analysis_date,
            DEFAULT_PROCUREMENT_CONFIG,
        )
        out.append(performance.to_dict())
    return out


async def get_inventory_kpis(context: ToolContext) -> dict[str, Any]:
    """Standard inventory KPIs with numerator/denominator provenance."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    kpis = await run_in_threadpool(_inventory_kpis, frames, analysis_date)
    limitations: list[str] = []
    if not any(kpis.values()):
        limitations.append("No inventory history was available for KPIs.")
    return {
        "data": {
            "analysis_date": analysis_date.isoformat(),
            "kpis": kpis,
        },
        "source": "inventory_snapshots+inventory_transactions",
        "label": "synthetic",
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _inventory_kpis(frames, analysis_date) -> dict[str, list[dict[str, Any]]]:
    """Compute standard KPI families (threadpool-safe, pure CPU)."""
    snapshots = frames.snapshots
    transactions = frames.transactions
    return {
        "current_on_hand": [
            item.to_dict()
            for item in inventory_kpis.current_on_hand(snapshots)[: ctx.MAX_SERIES]
        ],
        "stockout_stats": [
            item.to_dict()
            for item in inventory_kpis.stockout_stats(snapshots)[: ctx.MAX_SERIES]
        ],
        "movement_summary": [
            item.to_dict()
            for item in inventory_kpis.movement_summary(transactions)[: ctx.MAX_SERIES]
        ],
    }


async def get_data_quality_report(context: ToolContext) -> dict[str, Any]:
    """Counts plus persisted quality checks (read-only path)."""
    report = await build_quality_report(
        context.session, GenerationConfig(), results=[]
    )
    data = report.to_dict()
    return {
        "data": data,
        "source": "data_quality_checks",
        "label": "derived",
        "limitations": [
            "Counts are read from the database at request time; checks are "
            "the persisted results of the last generation run.",
        ],
    }


async def get_risk_report(context: ToolContext) -> dict[str, Any]:
    """Phase 7 risk register summary (integrated end-to-end evidence)."""
    params = context.params
    scope = await ctx.load_org_scope(context.session, context.auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=params.get("product_id"),
        warehouse_id=params.get("warehouse_id"),
        supplier_id=params.get("supplier_id"),
    )
    frames = await ctx.load_frames(context.session, scope)
    analysis_date = ctx.resolve_analysis_date(frames, params.get("analysis_date"))
    horizon = int(params.get("horizon_days") or 28)
    forecasts = await ctx.build_forecasts(
        context.session,
        frames,
        scope,
        analysis_date,
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    report = await run_in_threadpool(
        _risk_report_sync,
        frames,
        forecasts,
        analysis_date,
        horizon,
        params.get("severity"),
        params.get("domain"),
        params.get("supplier_id"),
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    register = list(report.get("register") or [])
    view = {key: value for key, value in report.items() if key != "register"}
    view["register"] = register[:MAX_REGISTER_RECORDS]
    limitations = [
        "Risk records are deterministic signals over synthetic data with "
        "their own evidence fields; they are not predictions of real events.",
    ]
    if len(register) > MAX_REGISTER_RECORDS:
        limitations.append(
            f"Register truncated to {MAX_REGISTER_RECORDS} of "
            f"{len(register)} records (deterministic order)."
        )
    if not register:
        limitations.append("No risk records matched the requested filters.")
    return {
        "data": view,
        "source": "risk_register",
        "label": "synthetic",
        "limitations": limitations,
        "analysis_date": analysis_date.isoformat(),
    }


def _risk_report_sync(
    frames,
    forecasts,
    analysis_date,
    horizon,
    severity,
    domain,
    supplier_id,
    product_id,
    warehouse_id,
) -> dict[str, Any]:
    """Full Phase 7 composition (threadpool-safe, pure CPU)."""
    from backend.app.analytics.procurement import concentration as concentration_mod
    from backend.app.analytics.procurement import inbound as inbound_mod
    from backend.app.analytics.procurement import reports as procurement_reports

    intelligence = []
    for key in sorted(forecasts):
        series_product, series_warehouse = key.split("|", 1)
        intelligence.append(
            intel_reports.build_intelligence(
                series_product,
                series_warehouse,
                frames.snapshots,
                frames.transactions,
                frames.demand,
                forecasts[key],
                frames.shipments,
                frames.po_lines,
                analysis_date,
                DEFAULT_INVENTORY_CONFIG,
            )
        )
    supplier_ids = (
        sorted(frames.supplier_links["supplier_id"].astype(str).unique().tolist())
        if not frames.supplier_links.empty
        else []
    )
    names = (
        dict(
            zip(
                frames.supplier_links["supplier_id"].astype(str),
                frames.supplier_links["supplier_name"].astype(str),
            )
        )
        if not frames.supplier_links.empty
        else {}
    )
    supplier_results = [
        procurement_reports.build_supplier_result(
            supplier_id_value,
            names.get(supplier_id_value, supplier_id_value),
            frames.po_lines,
            frames.shipments,
            frames.supplier_links,
            intelligence,
            analysis_date,
            DEFAULT_PROCUREMENT_CONFIG,
        )
        for supplier_id_value in supplier_ids
    ]
    open_orders = [
        order
        for result in supplier_results
        for order in result.open_orders
    ]
    cooccurrences = [
        impact
        for result in supplier_results
        for impact in result.service_impacts
    ]
    horizon_end = (
        analysis_date.fromordinal(analysis_date.toordinal() + horizon)
    ).isoformat()
    records: list[Any] = []
    for item in intelligence:
        coverage = inbound_mod.describe_inbound_coverage(
            item.product_id,
            item.warehouse_id,
            item.forecast,
            item.position.current_on_hand if item.position else None,
            open_orders,
            horizon_end,
        )
        own_impacts = [
            impact
            for impact in cooccurrences
            if impact.product_id == item.product_id
            and impact.warehouse_id == item.warehouse_id
        ]
        records.extend(
            risk_reports.build_series_records(
                item, coverage, DEFAULT_RISK_CONFIG, own_impacts
            )
        )
    for result in supplier_results:
        records.extend(
            risk_reports.build_supplier_records(
                result,
                frames.supplier_links,
                frames.po_lines,
                frames.shipments,
                analysis_date,
                DEFAULT_RISK_CONFIG,
            )
        )
    concentration_rows = list(concentration_mod.volume_shares(frames.po_lines, "spend"))
    concentration_rows.extend(concentration_mod.po_count_shares(frames.po_lines))
    records.extend(
        risk_reports.build_structural_records(
            frames.supplier_links,
            frames.snapshots,
            intelligence,
            concentration_rows,
            analysis_date,
            DEFAULT_RISK_CONFIG,
        )
    )
    records = risk_register.filter_records(
        records,
        severity=severity,
        domain=domain,
        supplier_id=supplier_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        include_unknown=True,
    )
    period = {"start": None, "end": None}
    report = risk_reports.build_report(
        records, analysis_date, horizon, period, DEFAULT_RISK_CONFIG
    )
    report.setdefault("generated_at", datetime.now(UTC).isoformat())
    return report


__all__ = [
    "get_data_quality_report",
    "get_forecast",
    "get_inventory_health",
    "get_inventory_kpis",
    "get_inventory_position",
    "get_risk_report",
    "get_supplier_scorecard",
]

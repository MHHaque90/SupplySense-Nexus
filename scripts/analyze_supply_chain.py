"""CLI for SupplySense Nexus analytics foundation (Phase 3).

SYNTHETIC DATA — the synthetic dataset shows illustrative patterns only.
Nothing here describes real business performance.

Examples:
    python scripts/analyze_supply_chain.py demand --aggregation week
    python scripts/analyze_supply_chain.py inventory
    python scripts/analyze_supply_chain.py procurement
    python scripts/analyze_supply_chain.py forecast --forecast-horizon 28
    python scripts/analyze_supply_chain.py report --output-markdown analytics_report.md
    python scripts/analyze_supply_chain.py inventory-intelligence --output-markdown inventory.md
    python scripts/analyze_supply_chain.py decision-replay --scenario SUPPLIER_OUTAGE --output-markdown replay.md
    python scripts/analyze_supply_chain.py optimization --scenario SUPPLIER_OUTAGE --objective minimize_total_cost --output-markdown plan.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.datasets import demand as demand_ds
from backend.app.analytics.datasets import inventory as inventory_ds
from backend.app.analytics.datasets import procurement as procurement_ds
from backend.app.analytics.datasets import sales as sales_ds
from backend.app.analytics.datasets import suppliers as suppliers_ds
from backend.app.analytics.features.profiles import profile_dataset
from backend.app.analytics.kpis import demand_kpis, inventory_kpis, procurement_kpis
from backend.app.analytics.reports.analytics_report import build_analytics_report, render_markdown
from backend.app.core.database import AsyncSessionLocal, dispose_engine, run_async


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD inclusive.")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD inclusive.")
    parser.add_argument("--product-id", default=None)
    parser.add_argument("--warehouse-id", default=None)
    parser.add_argument("--supplier-id", default=None)


def _parse_day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


async def _check_connection() -> bool:
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str))


async def _cmd_demand(args: argparse.Namespace) -> int:
    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    async with AsyncSessionLocal() as session:
        frame = await demand_ds.load_demand(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    if frame.empty:
        print("Dataset is empty for the requested filters.")
        return 1
    aggregated = demand_ds.aggregate_demand(frame, args.aggregation)
    kpis = [k.to_dict() for k in demand_kpis.demand_summary(frame)]
    profiles = [p.to_dict() for p in profile_dataset(frame)]
    _emit({"kpis": kpis, "rows": len(aggregated), "profiles": profiles[:25],
           "profile_total": len(profiles), "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER})
    return 0


async def _cmd_inventory(args: argparse.Namespace) -> int:
    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    async with AsyncSessionLocal() as session:
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        transactions = await inventory_ds.load_transactions(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    if snapshots.empty:
        print("Dataset is empty for the requested filters.")
        return 1
    kpis = []
    kpis.extend(inventory_kpis.inventory_levels(snapshots))
    kpis.extend(inventory_kpis.stockout_stats(snapshots))
    kpis.extend(inventory_kpis.turnover_proxy(transactions, snapshots))
    kpis.extend(inventory_kpis.movement_summary(transactions))
    kpis.extend(inventory_kpis.reconciliation_status(transactions, snapshots))
    _emit({"kpis": [k.to_dict() for k in kpis],
           "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER})
    return 0


async def _cmd_procurement(args: argparse.Namespace) -> int:
    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    async with AsyncSessionLocal() as session:
        orders = await procurement_ds.load_purchase_orders(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        links = await suppliers_ds.load_suppliers(
            session, [args.supplier_id] if args.supplier_id else None
        )
    if orders.empty:
        print("Dataset is empty for the requested filters.")
        return 1
    kpis = []
    kpis.extend(procurement_kpis.procurement_summary(orders))
    kpis.extend(procurement_kpis.lead_time_stats(orders))
    kpis.extend(procurement_kpis.shipment_performance(shipments))
    kpis.extend(procurement_kpis.moq_compliance(orders))
    kpis.extend(procurement_kpis.concentration(orders))
    _emit({"kpis": [k.to_dict() for k in kpis], "supplier_links": len(links),
           "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER})
    return 0


async def _cmd_forecast(args: argparse.Namespace) -> int:
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.features.demand_features import ensure_daily_continuity
    from backend.app.analytics.forecasting import persistence as persistence_mod
    from backend.app.analytics.reports.forecasting_report import evaluate_one_series

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    if args.model is not None and args.model not in persistence_mod.MODEL_NAMES:
        print(f"Unsupported model: {args.model}. Valid: {sorted(persistence_mod.MODEL_NAMES)}")
        return 2
    config = AnalyticsConfig(forecast_horizon=args.forecast_horizon,
                             comparison_metric=args.metric,
                             min_history=args.min_history)
    async with AsyncSessionLocal() as session:
        frame = await demand_loader.load_demand(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    if frame.empty:
        print("Dataset is empty for the requested filters.")
        return 1
    grouped = frame.groupby(["product_id", "warehouse_id"])
    if args.product_id and args.warehouse_id:
        key = (args.product_id, args.warehouse_id)
        if key not in grouped.groups:
            print("Requested product/warehouse series does not exist.")
            return 1
        chosen = [(key, grouped.get_group(key))]
    else:
        volumes = grouped["quantity"].sum().sort_values(ascending=False)
        key = volumes.index[0]
        chosen = [(key, grouped.get_group(key))]
    series_key, group = chosen[0]
    ordered = group.sort_values("date")
    if ordered.duplicated(subset=["date"]).any():
        print("Duplicate date observations for the series; refusing to forecast.")
        return 1
    values = [float(v) for v in ordered["quantity"].tolist()]
    full = ensure_daily_continuity(
        ordered[["product_id", "warehouse_id", "date", "quantity"]].copy()
    )
    warnings = []
    if int(full["was_imputed_zero"].sum()) > 0:
        warnings.append("Missing calendar dates zero-filled (documented imputation).")
    values = [float(v) for v in full["quantity"].tolist()]
    origin = full["date"].max()
    if args.validation_windows and args.validation_windows > 0:
        span = len(values) - config.min_history - config.forecast_horizon
        step = max(1, span // args.validation_windows) if span > 0 else config.validation_step
        config = AnalyticsConfig(
            forecast_horizon=config.forecast_horizon,
            comparison_metric=config.comparison_metric,
            min_history=config.min_history,
            validation_step=step,
        )
    try:
        import pandas as pd

        evaluation = evaluate_one_series(
            values,
            f"{series_key[0]}|{series_key[1]}",
            series_key[0],
            series_key[1],
            origin,
            config,
            season=args.season,
            include_ml=args.include_ml,
            force_model=args.model,
            dates=pd.DatetimeIndex(pd.to_datetime(full["date"])),
        )
    except ValueError as exc:
        print(f"Insufficient history: {exc}")
        return 1
    evaluation["forecast"]["warnings"] = warnings + evaluation["forecast"]["warnings"]
    persisted: dict[str, object] = {}
    if args.persist:
        from backend.app.analytics.forecasting.result import ForecastOutput, SelectionResult

        payload = evaluation["forecast"]
        output = ForecastOutput(**{
            key: payload[key] for key in ForecastOutput.__dataclass_fields__ if key in payload
        })
        sel = evaluation["selection"]
        selection = SelectionResult(**{
            key: sel[key] for key in SelectionResult.__dataclass_fields__ if key in sel
        })
        async with AsyncSessionLocal() as session:
            try:
                version = await persistence_mod.ensure_model_version(
                    session, selection, str(full["date"].min()), str(origin)
                )
                run = await persistence_mod.record_forecast_run(
                    session, version.id, selection, str(full["date"].min()), str(origin)
                )
                counts = await persistence_mod.persist_forecast(session, output, version.id)
                await session.commit()
                persisted = {"model_version_id": version.id, "forecast_run_id": run.id, **counts}
            except Exception:
                await session.rollback()
                raise
    _emit({**evaluation, "persisted": persisted,
           "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER})
    if args.output:
        Path(args.output).write_text(
            json.dumps({**evaluation, "persisted": persisted}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Wrote {args.output}")
    return 0


async def _cmd_forecast_report(args: argparse.Namespace) -> int:
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.reports.forecasting_report import evaluate_dataset, render_markdown

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    config = AnalyticsConfig(forecast_horizon=args.forecast_horizon,
                             comparison_metric=args.metric,
                             min_history=args.min_history)
    async with AsyncSessionLocal() as session:
        frame = await demand_loader.load_demand(session, start, end)
    if frame.empty:
        print("Dataset is empty for the requested filters.")
        return 1
    origin = frame["date"].max()
    series: dict[str, dict[str, object]] = {}
    for (product_id, warehouse_id), group in frame.groupby(["product_id", "warehouse_id"]):
        ordered = group.sort_values("date")
        series[f"{product_id}|{warehouse_id}"] = {
            "values": [float(v) for v in ordered["quantity"].tolist()],
            "product_id": str(product_id),
            "warehouse_id": str(warehouse_id),
            "training_start": str(ordered["date"].min()),
            "training_end": str(ordered["date"].max()),
        }
    report = evaluate_dataset(
        series, origin, config, season=args.season,
        include_ml=args.include_ml, max_series=args.max_series,
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(render_markdown(report), encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        summary = {k: v for k, v in report.items() if k != "evaluations"}
        _emit(summary)
    return 0


async def _cmd_report(args: argparse.Namespace) -> int:
    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    config = AnalyticsConfig(forecast_horizon=args.forecast_horizon)
    async with AsyncSessionLocal() as session:
        demand_frame = await demand_ds.load_demand(session, start, end)
        if demand_frame.empty:
            print("Dataset is empty for the requested filters.")
            return 1
        snapshots = await inventory_ds.load_snapshots(session, start, end)
        transactions = await inventory_ds.load_transactions(session, start, end)
        orders = await procurement_ds.load_purchase_orders(session, start, end)
        shipments = await procurement_ds.load_shipments(session, start, end)
        sales_orders = await sales_ds.load_sales_orders(session, start, end)
        sales_lines = await sales_ds.load_sales_lines(session, start, end)
    volumes = demand_frame.groupby(["product_id", "warehouse_id"])["quantity"].sum()
    top_key = volumes.sort_values(ascending=False).index[0]
    top_values = demand_frame[
        (demand_frame["product_id"] == top_key[0])
        & (demand_frame["warehouse_id"] == top_key[1])
    ].sort_values("date")["quantity"].astype(float).tolist()
    report = build_analytics_report(
        demand_frame, snapshots, transactions, orders, shipments,
        sales_orders, sales_lines, config,
        forecast_series_id=f"{top_key[0]}|{top_key[1]}",
        forecast_values=[float(v) for v in top_values],
        dataset_config={"seed": 42, "generator_version": "2.0.0"},
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(render_markdown(report), encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit(report)
    return 0


async def _cmd_inventory_intelligence(args: argparse.Namespace) -> int:
    from backend.app.analytics.config import AnalyticsConfig
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import (
        aging,
        anomalies,
        concentration,
        forecast_inputs,
        turnover,
    )
    from backend.app.analytics.inventory import (
        reports as intel_reports,
    )
    from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    config = DEFAULT_INVENTORY_CONFIG
    forecast_config = AnalyticsConfig(
        forecast_horizon=args.forecast_horizon, min_history=args.min_history
    )
    async with AsyncSessionLocal() as session:
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if snapshots.empty:
            print("Inventory dataset is empty for the requested filters.")
            return 1
        analysis_date = end or pd.to_datetime(snapshots["snapshot_date"]).max().date()
        transactions = await inventory_ds.load_transactions(
            session, None, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        shipments = await procurement_ds.load_shipments(
            session, analysis_date, None,
            [args.supplier_id] if args.supplier_id else None,
        )
        po_lines = await procurement_ds.load_purchase_orders(session, start, analysis_date)
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date
        ].iterrows()
    })
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis_date, forecast_config,
                season=args.season, max_series=args.max_series,
            )
    inputs: dict[str, object] = dict(persisted_inputs)
    inputs.update(generated)
    origin_str = analysis_date.isoformat()
    results = []
    for product_id, warehouse_id in series_keys:
        key = f"{product_id}|{warehouse_id}"
        forecast = inputs.get(key)
        if forecast is None:
            forecast = forecast_inputs.missing_forecast(product_id, warehouse_id, origin_str)
        results.append(intel_reports.build_intelligence(
            product_id, warehouse_id, snapshots, transactions, demand_frame,
            forecast, shipments, po_lines, analysis_date, config,
        ))
    if args.health:
        wanted = args.health.upper()
        results = [r for r in results if r.health and r.health.health == wanted]
    anomalies_list = []
    turnover_rows = []
    aging_rows = []
    for result in results:
        for anomaly in anomalies.detect_anomalies(
            result.product_id, result.warehouse_id, snapshots, transactions,
            analysis_date, config,
        ):
            anomalies_list.append(anomaly.to_dict())
        stats = turnover.series_turnover(
            result.product_id, result.warehouse_id, transactions, snapshots
        )
        turnover_rows.append({"product_id": result.product_id,
                              "warehouse_id": result.warehouse_id, **stats})
        movement = aging.days_since_movement(
            result.product_id, result.warehouse_id, transactions, analysis_date
        )
        aging_rows.append({"product_id": result.product_id,
                           "warehouse_id": result.warehouse_id, **movement})
    concentration_rows = {
        "by_warehouse": concentration.concentration_by_warehouse(snapshots),
        "by_product": concentration.concentration_by_product(snapshots),
    }
    report = intel_reports.build_report(
        results, anomalies_list, turnover_rows, aging_rows, concentration_rows,
        analysis_date, args.forecast_horizon, config,
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(intel_reports.render_markdown(report),
                                              encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit({**report, "results": report["results"][:10],
               "results_truncated": len(report["results"])})
    return 0


async def _cmd_procurement_intelligence(args: argparse.Namespace) -> int:
    from backend.app.analytics.config import AnalyticsConfig
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import forecast_inputs
    from backend.app.analytics.inventory import reports as intel_reports
    from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
    from backend.app.analytics.procurement import (
        concentration as concentration_mod,
    )
    from backend.app.analytics.procurement import (
        inbound as inbound_mod,
    )
    from backend.app.analytics.procurement import (
        reports as procurement_reports,
    )
    from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    config = DEFAULT_PROCUREMENT_CONFIG
    forecast_config = AnalyticsConfig(
        forecast_horizon=args.forecast_horizon, min_history=args.min_history
    )
    async with AsyncSessionLocal() as session:
        supplier_links = await suppliers_ds.load_suppliers(
            session,
            [args.supplier_id] if args.supplier_id else None,
        )
        po_lines = await procurement_ds.load_purchase_orders(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if supplier_links.empty and po_lines.empty:
            print("Procurement dataset is empty for the requested filters.")
            return 1
        latest_po = pd.to_datetime(po_lines["order_date"]).max().date() if not po_lines.empty else None
        latest_snap = pd.to_datetime(snapshots["snapshot_date"]).max().date() if not snapshots.empty else None
        candidates = [day for day in (end, latest_snap, latest_po) if day is not None]
        if not candidates:
            print("No dated records for the requested filters.")
            return 1
        analysis_date = min(candidates) if end else max(candidates)
        transactions = await inventory_ds.load_transactions(
            session, None, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    # Phase 5 intelligence per series (consumed, not modified).
    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date
        ].iterrows()
    }) if not snapshots.empty else []
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing and not demand_frame.empty:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis_date, forecast_config,
                season=args.season, max_series=args.max_series,
            )
    inputs: dict[str, object] = dict(persisted_inputs)
    inputs.update(generated)
    origin_str = analysis_date.isoformat()
    intelligence = []
    for product_id, warehouse_id in series_keys:
        key = f"{product_id}|{warehouse_id}"
        forecast = inputs.get(key)
        if forecast is None:
            forecast = forecast_inputs.missing_forecast(product_id, warehouse_id, origin_str)
        intelligence.append(intel_reports.build_intelligence(
            product_id, warehouse_id, snapshots, transactions, demand_frame,
            forecast, shipments, po_lines, analysis_date, DEFAULT_INVENTORY_CONFIG,
        ))
    supplier_ids = sorted(supplier_links["supplier_id"].astype(str).unique().tolist())
    if args.max_suppliers is not None:
        supplier_ids = supplier_ids[: max(0, args.max_suppliers)]
    supplier_names = dict(zip(
        supplier_links["supplier_id"].astype(str), supplier_links["supplier_name"].astype(str)
    ))
    results = []
    for supplier_id in supplier_ids:
        result = procurement_reports.build_supplier_result(
            supplier_id, str(supplier_names.get(supplier_id, supplier_id)),
            po_lines, shipments, supplier_links, intelligence, analysis_date, config,
        )
        if args.skip_open_orders:
            result.open_orders = []
        results.append(result)
    horizon_end = analysis_date.fromordinal(
        analysis_date.toordinal() + args.forecast_horizon
    ).isoformat()
    open_all = [order for result in results for order in result.open_orders]
    inbound_states = []
    if args.include_exposure:
        for item in intelligence:
            coverage_in = inbound_mod.describe_inbound_coverage(
                item.product_id, item.warehouse_id, item.forecast,
                item.position.current_on_hand if item.position else None,
                open_all, horizon_end,
            )
            inbound_states.append(coverage_in.to_dict())
    concentration_rows = []
    if args.include_concentration:
        for row in concentration_mod.volume_shares(po_lines, "spend"):
            concentration_rows.append(row.to_dict())
        for row in concentration_mod.volume_shares(po_lines, "quantity"):
            concentration_rows.append(row.to_dict())
        for row in concentration_mod.po_count_shares(po_lines):
            concentration_rows.append(row.to_dict())
    category_of = {}
    if not demand_frame.empty and "category" in demand_frame.columns:
        category_of = dict(zip(
            demand_frame["product_id"].astype(str), demand_frame["category"].astype(str)
        ))
    for row in concentration_mod.category_concentration(po_lines, category_of):
        concentration_rows.append(row.to_dict())
    supplier_product_map = {
        str(supplier): set(group["product_id"].astype(str).tolist())
        for supplier, group in supplier_links.groupby("supplier_id")
    }
    for row in concentration_mod.exposure_concentration(intelligence, supplier_product_map, config):
        concentration_rows.append(row.to_dict())
    dependency_classes = concentration_mod.dependency_classes(supplier_links)
    period: dict[str, str | None] = {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    }
    report = procurement_reports.build_report(
        results, concentration_rows, dependency_classes, inbound_states,
        analysis_date, args.forecast_horizon, period, config,
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(procurement_reports.render_markdown(report),
                                              encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit({**report, "results": report["results"][:5],
               "results_truncated": len(report["results"])})
    return 0


async def _cmd_risk_intelligence(args: argparse.Namespace) -> int:
    from backend.app.analytics.config import AnalyticsConfig
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import forecast_inputs
    from backend.app.analytics.inventory import reports as intel_reports
    from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
    from backend.app.analytics.procurement import concentration as concentration_mod
    from backend.app.analytics.procurement import inbound as inbound_mod
    from backend.app.analytics.procurement import reports as procurement_reports
    from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
    from backend.app.analytics.risk import register as risk_register
    from backend.app.analytics.risk import reports as risk_reports
    from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    forecast_config = AnalyticsConfig(
        forecast_horizon=args.forecast_horizon, min_history=args.min_history
    )
    async with AsyncSessionLocal() as session:
        supplier_links = await suppliers_ds.load_suppliers(
            session,
            [args.supplier_id] if args.supplier_id else None,
        )
        po_lines = await procurement_ds.load_purchase_orders(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if snapshots.empty and po_lines.empty:
            print("Dataset is empty for the requested filters.")
            return 1
        latest_snap = pd.to_datetime(snapshots["snapshot_date"]).max().date() \
            if not snapshots.empty else None
        latest_po = pd.to_datetime(po_lines["order_date"]).max().date() \
            if not po_lines.empty else None
        candidates = [day for day in (end, latest_snap, latest_po) if day is not None]
        if not candidates:
            print("No dated records for the requested filters.")
            return 1
        analysis_date = min(candidates) if end else max(candidates)
        transactions = await inventory_ds.load_transactions(
            session, None, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date
        ].iterrows()
    }) if not snapshots.empty else []
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing and not demand_frame.empty:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis_date, forecast_config,
                season=args.season, max_series=args.max_series,
            )
    inputs: dict[str, object] = dict(persisted_inputs)
    inputs.update(generated)
    origin_str = analysis_date.isoformat()
    intelligence = []
    for product_id, warehouse_id in series_keys:
        key = f"{product_id}|{warehouse_id}"
        forecast = inputs.get(key)
        if forecast is None:
            forecast = forecast_inputs.missing_forecast(product_id, warehouse_id, origin_str)
        intelligence.append(intel_reports.build_intelligence(
            product_id, warehouse_id, snapshots, transactions, demand_frame,
            forecast, shipments, po_lines, analysis_date, DEFAULT_INVENTORY_CONFIG,
        ))
    supplier_ids = sorted(supplier_links["supplier_id"].astype(str).unique().tolist()) \
        if not supplier_links.empty else []
    if args.max_suppliers is not None:
        supplier_ids = supplier_ids[: max(0, args.max_suppliers)]
    supplier_names = dict(zip(
        supplier_links["supplier_id"].astype(str),
        supplier_links["supplier_name"].astype(str),
    )) if not supplier_links.empty else {}
    supplier_results = []
    for supplier_id in supplier_ids:
        supplier_results.append(procurement_reports.build_supplier_result(
            supplier_id, str(supplier_names.get(supplier_id, supplier_id)),
            po_lines, shipments, supplier_links, intelligence,
            analysis_date, DEFAULT_PROCUREMENT_CONFIG,
        ))
    horizon_end = analysis_date.fromordinal(
        analysis_date.toordinal() + args.forecast_horizon
    ).isoformat()
    open_all = [order for result in supplier_results for order in result.open_orders]
    cooccurrences = [
        impact for result in supplier_results for impact in result.service_impacts
    ]
    records = []
    for item in intelligence:
        coverage_in = inbound_mod.describe_inbound_coverage(
            item.product_id, item.warehouse_id, item.forecast,
            item.position.current_on_hand if item.position else None,
            open_all, horizon_end,
        )
        own_cooccurrences = [
            impact for impact in cooccurrences
            if impact.product_id == item.product_id
            and impact.warehouse_id == item.warehouse_id
        ]
        records.extend(risk_reports.build_series_records(
            item, coverage_in, DEFAULT_RISK_CONFIG, own_cooccurrences
        ))
    for result in supplier_results:
        records.extend(risk_reports.build_supplier_records(
            result, supplier_links, po_lines, shipments,
            analysis_date, DEFAULT_RISK_CONFIG,
        ))
    concentration_rows = []
    for row in concentration_mod.volume_shares(po_lines, "spend"):
        concentration_rows.append(row)
    for row in concentration_mod.po_count_shares(po_lines):
        concentration_rows.append(row)
    records.extend(risk_reports.build_structural_records(
        supplier_links, snapshots, intelligence, concentration_rows,
        analysis_date, DEFAULT_RISK_CONFIG,
    ))
    records = risk_register.filter_records(
        records,
        severity=args.severity,
        domain=args.domain,
        supplier_id=args.supplier_id,
        product_id=args.product_id,
        warehouse_id=args.warehouse_id,
        include_unknown=args.include_unknown and not args.exclude_unknown,
    )
    period: dict[str, str | None] = {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    }
    report = risk_reports.build_report(
        records, analysis_date, args.forecast_horizon, period, DEFAULT_RISK_CONFIG
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(risk_reports.render_markdown(report),
                                              encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        view = dict(report)
        if not args.include_evidence:
            view = {**report, "register": []}
        _emit(view)
    return 0


async def _cmd_disruption_simulation(args: argparse.Namespace) -> int:
    from backend.app.analytics.config import AnalyticsConfig
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import forecast_inputs
    from backend.app.analytics.simulation import events as events_mod
    from backend.app.analytics.simulation import reports as sim_reports
    from backend.app.analytics.simulation import runner as runner_mod
    from backend.app.analytics.simulation import scenarios as scenarios_mod
    from backend.app.analytics.simulation import targets as targets_mod
    from backend.app.analytics.simulation.types import (
        DEFAULT_SIMULATION_CONFIG,
        DisruptionEvent,
        DistributionAssumption,
    )

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    if args.horizon_days is not None and not 1 <= args.horizon_days <= 180:
        print("Invalid --horizon-days: must be within [1, 180].")
        return 2
    horizon = args.horizon_days or DEFAULT_SIMULATION_CONFIG.default_horizon_days
    # Build the event from a template, explicit parameters, or components.
    try:
        components = []
        for raw in args.component or []:
            payload = json.loads(raw)
            component = DisruptionEvent(
                event_id=f"{args.scenario}-component-{payload.get('event_type', 'UNKNOWN')}",
                event_type=payload.get("event_type", ""),
                name=payload.get("name", ""),
                start_date="",
                duration_days=int(payload.get("duration_days", 14)),
                affected_suppliers=list(payload.get("affected_suppliers", []) or []),
                affected_products=list(payload.get("affected_products", []) or []),
                affected_warehouses=list(payload.get("affected_warehouses", []) or []),
                supply_reduction=float(payload.get("supply_reduction", 0.0)),
                lead_time_delay_days=int(payload.get("lead_time_delay_days", 0)),
                demand_multiplier=float(payload.get("demand_multiplier", 1.0)),
                warehouse_available=bool(payload.get("warehouse_available", True)),
            )
            events_mod.validate_event(component)
            components.append(component)
        if args.scenario and not components:
            event = events_mod.apply_template(
                args.scenario,
                event_id=f"{args.scenario}-event",
                start_date="",
                **{
                    key: value for key, value in {
                        "duration_days": args.duration_days,
                        "supply_reduction": args.supply_reduction,
                        "lead_time_delay_days": args.lead_time_delay_days,
                        "demand_multiplier": args.demand_multiplier,
                    }.items() if value is not None
                },
            )
        else:
            event = DisruptionEvent(
                event_id=f"{args.event_type}-event",
                event_type=args.event_type,
                name=args.event_type,
                start_date="",
                duration_days=args.duration_days or 14,
                affected_suppliers=[args.supplier_id] if args.supplier_id else [],
                affected_products=[args.product_id] if args.product_id else [],
                affected_warehouses=[args.warehouse_id] if args.warehouse_id else [],
                supply_reduction=args.supply_reduction or 0.0,
                lead_time_delay_days=args.lead_time_delay_days or 0,
                demand_multiplier=args.demand_multiplier or 1.0,
                warehouse_available=False if args.event_type == "WAREHOUSE_DISRUPTION" else True,
                components=components,
            )
            # Targeting resolves at scenario assembly; check values now.
            events_mod.validate_event(event, check_targets=False)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid event parameters: {exc}")
        return 2
    distributions = []
    if args.duration_min is not None or args.duration_max is not None:
        if args.duration_min is None or args.duration_max is None or args.duration_mode is None:
            print("Duration distribution needs --duration-min, --duration-mode, and --duration-max.")
            return 2
        distributions.append(DistributionAssumption(
            parameter="duration_days", distribution="triangular",
            minimum=float(args.duration_min), mode=float(args.duration_mode),
            maximum=float(args.duration_max), units="days",
        ))
    if args.reduction_min is not None or args.reduction_max is not None:
        if args.reduction_min is None or args.reduction_max is None:
            print("Reduction distribution needs --reduction-min and --reduction-max.")
            return 2
        distributions.append(DistributionAssumption(
            parameter="supply_reduction", distribution="uniform",
            minimum=float(args.reduction_min), maximum=float(args.reduction_max),
            units="fraction",
        ))
    event.distributions = distributions
    for assumption in distributions:
        try:
            from backend.app.analytics.simulation import probability as probability_mod

            probability_mod.validate_distribution(assumption)
        except ValueError as exc:
            print(f"Invalid distribution: {exc}")
            return 2
    async with AsyncSessionLocal() as session:
        supplier_links = await suppliers_ds.load_suppliers(
            session,
            [args.supplier_id] if args.supplier_id else None,
        )
        po_lines = await procurement_ds.load_purchase_orders(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end,
            [args.supplier_id] if args.supplier_id else None,
        )
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if snapshots.empty and po_lines.empty:
            print("Dataset is empty for the requested filters.")
            return 1
        latest_snap = pd.to_datetime(snapshots["snapshot_date"]).max().date() \
            if not snapshots.empty else None
        latest_po = pd.to_datetime(po_lines["order_date"]).max().date() \
            if not po_lines.empty else None
        candidates = [day for day in (end, latest_snap, latest_po) if day is not None]
        if not candidates:
            print("No dated records for the requested filters.")
            return 1
        analysis_date = min(candidates) if end else max(candidates)
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    # Resolve targets: explicit IDs, supplier expansion, or risk records.
    entities = targets_mod.resolve_explicit(
        supplier_ids=[args.supplier_id] if args.supplier_id else [],
        product_ids=[args.product_id] if args.product_id else [],
        warehouse_ids=[args.warehouse_id] if args.warehouse_id else [],
    )
    selection_basis = "explicit_user_selection"
    for risk_id in args.risk_id or []:
        parts = risk_id.split(":")
        record = {"risk_id": risk_id}
        if len(parts) >= 4:
            record["supplier_id"] = None
            record["product_id"] = None
            record["warehouse_id"] = None
            # risk_id format: domain:entity_type:entity_id:date
            entity_type, entity_id = parts[1], parts[2]
            if entity_type == "supplier":
                record["supplier_id"] = entity_id
            elif entity_type == "product":
                record["product_id"] = entity_id
            elif entity_type == "warehouse":
                record["warehouse_id"] = entity_id
            elif entity_type == "product_warehouse" and "|" in entity_id:
                product, warehouse = entity_id.split("|", 1)
                record["product_id"] = product
                record["warehouse_id"] = warehouse
        resolved, basis = targets_mod.resolve_risk_record(record)
        entities.extend(resolved)
        selection_basis = basis
    if args.supplier_id:
        entities.extend(targets_mod.resolve_supplier_products(args.supplier_id, supplier_links))
    try:
        scenario = scenarios_mod.build_scenario(
            scenario_id=args.scenario_id or f"scenario-{event.event_type.lower()}",
            event=event,
            analysis_date=analysis_date.isoformat(),
            horizon_days=horizon,
            affected_entities=entities,
            probability_mode=args.probability_mode,
            probability=args.probability,
            simulation_count=args.simulation_count,
            random_seed=args.random_seed,
            selection_basis=selection_basis,
            name=args.name or event.name,
        )
    except ValueError as exc:
        print(f"Invalid scenario: {exc}")
        return 2
    # Forecast inputs: persisted-first, generated fallback (frozen interfaces).
    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date
        ].iterrows()
    }) if not snapshots.empty else []
    wanted = {
        (str(item.get("product_id")), str(item.get("warehouse_id")))
        for item in entities if item.get("product_id") and item.get("warehouse_id")
    }
    if wanted:
        series_keys = sorted(set(series_keys) & wanted)
    if args.max_series is not None:
        series_keys = series_keys[: max(0, args.max_series)]
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing and not demand_frame.empty:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            forecast_config = AnalyticsConfig(
                forecast_horizon=horizon, min_history=args.min_history
            )
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis_date, forecast_config,
                season=args.season, max_series=args.max_series,
            )
    forecast_by_series: dict[str, object] = dict(persisted_inputs)
    forecast_by_series.update(generated)
    # Restrict forecasts to targeted series when targeting is explicit.
    if wanted:
        forecast_by_series = {
            key: value for key, value in forecast_by_series.items()
            if tuple(key.split("|", 1)) in wanted
        }
    try:
        result = runner_mod.run_scenario(
            scenario, forecast_by_series, snapshots, shipments, po_lines,
            supplier_links, analysis_date, DEFAULT_SIMULATION_CONFIG,
        )
    except ValueError as exc:
        print(f"Cannot run scenario: {exc}")
        return 1
    report = sim_reports.build_report(
        scenario, result["baseline"], result["scenario"], result["deltas"],
        result["traces"], DEFAULT_SIMULATION_CONFIG.to_dict(),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, default=str),
                                          encoding="utf-8")
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(sim_reports.render_markdown(report),
                                              encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit(report)
    return 0


async def _cmd_decision_replay(args: argparse.Namespace) -> int:
    """Orchestrate one Decision Replay Lab run (no business logic here)."""
    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import forecast_inputs
    from backend.app.analytics.replay import replay as replay_mod
    from backend.app.analytics.replay import reports as replay_reports
    from backend.app.analytics.simulation import events as events_mod
    from backend.app.analytics.simulation import scenarios as scenarios_mod
    from backend.app.analytics.simulation import targets as targets_mod
    from backend.app.analytics.simulation.types import (
        DEFAULT_SIMULATION_CONFIG,
        DisruptionEvent,
    )

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    if args.horizon_days is not None and not 1 <= args.horizon_days <= 180:
        print("Invalid --horizon-days: must be within [1, 180].")
        return 2
    # Scenario definition: a JSON definition or a named Phase 8 template.
    scenario_payload: dict = {}
    if args.scenario_json:
        raw = args.scenario_json.strip()
        try:
            scenario_payload = (
                json.loads(raw) if raw.startswith("{")
                else json.loads(Path(raw).read_text(encoding="utf-8"))
            )
        except (ValueError, OSError) as exc:
            print(f"Invalid --scenario-json: {exc}")
            return 2
    event_payload = dict(scenario_payload.get("event") or {})
    try:
        if event_payload:
            event = DisruptionEvent(
                event_id=str(event_payload.get("event_id", "replay-event")),
                event_type=str(event_payload.get("event_type", "")),
                name=str(event_payload.get("name", "")),
                description=str(event_payload.get("description", "")),
                start_date=str(event_payload.get("start_date", "")),
                duration_days=int(event_payload.get("duration_days", 14)),
                affected_suppliers=list(event_payload.get("affected_suppliers", []) or []),
                affected_products=list(event_payload.get("affected_products", []) or []),
                affected_warehouses=list(
                    event_payload.get("affected_warehouses", []) or []
                ),
                supply_reduction=float(event_payload.get("supply_reduction", 0.0)),
                lead_time_delay_days=int(event_payload.get("lead_time_delay_days", 0)),
                demand_multiplier=float(event_payload.get("demand_multiplier", 1.0)),
                warehouse_available=bool(event_payload.get("warehouse_available", True)),
                assumptions=list(event_payload.get("assumptions", []) or []),
            )
            events_mod.validate_event(event, check_targets=False)
        elif args.scenario:
            event = events_mod.apply_template(
                args.scenario,
                event_id=f"{args.scenario}-event",
                start_date="",
                **{
                    key: value for key, value in {
                        "duration_days": args.duration_days,
                        "supply_reduction": args.supply_reduction,
                        "lead_time_delay_days": args.lead_time_delay_days,
                        "demand_multiplier": args.demand_multiplier,
                    }.items() if value is not None
                },
            )
        else:
            print("Provide --scenario-json or --scenario (named template).")
            return 2
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"Invalid scenario definition: {exc}")
        return 2
    async with AsyncSessionLocal() as session:
        supplier_links = await suppliers_ds.load_suppliers(
            session, [args.supplier_id] if args.supplier_id else None
        )
        po_lines = await procurement_ds.load_purchase_orders(
            session, start, end, [args.supplier_id] if args.supplier_id else None
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end, [args.supplier_id] if args.supplier_id else None
        )
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if snapshots.empty and po_lines.empty:
            print("Dataset is empty for the requested filters.")
            return 1
        latest_snap = pd.to_datetime(snapshots["snapshot_date"]).max().date() \
            if not snapshots.empty else None
        latest_po = pd.to_datetime(po_lines["order_date"]).max().date() \
            if not po_lines.empty else None
        candidates = [day for day in (end, latest_snap, latest_po) if day is not None]
        if not candidates:
            print("No dated records for the requested filters.")
            return 1
        analysis_date = min(candidates) if end else max(candidates)
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    scenario_analysis_date = scenario_payload.get("analysis_date")
    analysis = date.fromisoformat(scenario_analysis_date) if scenario_analysis_date \
        else analysis_date
    horizon = args.horizon_days or int(scenario_payload.get("horizon_days", 0)) \
        or DEFAULT_SIMULATION_CONFIG.default_horizon_days
    simulation_count = args.simulation_count or int(
        scenario_payload.get("simulation_count", 1)
    )
    random_seed = args.random_seed if args.random_seed is not None else int(
        scenario_payload.get("random_seed", 42)
    )
    entities = targets_mod.resolve_explicit(
        supplier_ids=[args.supplier_id] if args.supplier_id else [],
        product_ids=[args.product_id] if args.product_id else [],
        warehouse_ids=[args.warehouse_id] if args.warehouse_id else [],
    )
    if args.supplier_id:
        entities.extend(
            targets_mod.resolve_supplier_products(args.supplier_id, supplier_links)
        )
    if not entities and scenario_payload.get("affected_entities"):
        entities = list(scenario_payload["affected_entities"])
    scenario_id = args.scenario_id or str(
        scenario_payload.get("scenario_id") or f"replay-{event.event_type.lower()}"
    )
    try:
        scenario = scenarios_mod.build_scenario(
            scenario_id=scenario_id,
            event=event,
            analysis_date=analysis.isoformat(),
            horizon_days=horizon,
            affected_entities=entities,
            probability_mode=args.probability_mode,
            probability=args.probability,
            simulation_count=simulation_count,
            random_seed=random_seed,
            name=args.name or event.name,
        )
    except ValueError as exc:
        print(f"Invalid scenario: {exc}")
        return 2
    replay_id = replay_mod.resolve_replay_id(scenario)
    try:
        decision_list = _parse_replay_decisions(replay_id, args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Invalid decision definition: {exc}")
        return 2
    # Forecast inputs: persisted-first, generated fallback (frozen interfaces).
    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis
        ].iterrows()
    }) if not snapshots.empty else []
    wanted = {
        (str(item.get("product_id")), str(item.get("warehouse_id")))
        for item in entities if item.get("product_id") and item.get("warehouse_id")
    }
    if wanted:
        series_keys = sorted(set(series_keys) & wanted)
    if args.max_series is not None:
        series_keys = series_keys[: max(0, args.max_series)]
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing and not demand_frame.empty:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis, AnalyticsConfig(
                    forecast_horizon=args.forecast_horizon, min_history=args.min_history
                ),
                season=args.season, max_series=args.max_series,
            )
    forecast_by_series: dict[str, object] = dict(persisted_inputs)
    forecast_by_series.update(generated)
    if wanted:
        forecast_by_series = {
            key: value for key, value in forecast_by_series.items()
            if tuple(key.split("|", 1)) in wanted
        }
    try:
        replay_result = replay_mod.run_replay(
            scenario, decision_list, forecast_by_series, snapshots, shipments,
            po_lines, supplier_links, analysis, DEFAULT_SIMULATION_CONFIG,
            replay_id=replay_id,
        )
    except ValueError as exc:
        print(f"Cannot run replay: {exc}")
        return 1
    report = replay_reports.build_report(replay_result)
    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(
            replay_reports.render_markdown(report), encoding="utf-8"
        )
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit(report)
    return 0


def _parse_replay_decisions(replay_id: str, args: argparse.Namespace):
    """Parse repeated --decision JSON strings and --decision-file payloads."""
    from backend.app.analytics.replay import decisions as replay_decisions

    payloads: list[dict] = []
    for raw in args.decision or []:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("--decision must be a JSON object.")
        payloads.append(payload)
    for path in args.decision_file or []:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            payloads.append(data)
        elif isinstance(data, list):
            payloads.extend(data)
        else:
            raise ValueError(f"{path} must contain a JSON object or array.")
    parsed = [
        replay_decisions.decision_from_dict(replay_id, payload) for payload in payloads
    ]
    if not any(item.decision_type == "NO_ACTION" for item in parsed):
        # The control arm is always present so every replay is comparable.
        parsed.insert(0, replay_decisions.build_no_action(replay_id))
    return parsed


async def _cmd_optimization(args: argparse.Namespace) -> int:
    """Run one Optimization Engine analysis (Phase 10; no business logic here).

    Reuses Phase 9 scenario conventions with a Phase 10-owned code block,
    runs the replay with the NO_ACTION control arm only, then builds and
    solves the procurement MILP. Exit codes: 0 = analysis completed (any
    solver status, reported in the payload), 1 = no data / cannot build
    inputs, 2 = invalid arguments.
    """
    import time as time_mod

    from backend.app.analytics.datasets import demand as demand_loader
    from backend.app.analytics.inventory import forecast_inputs
    from backend.app.analytics.optimization import (
        OptimizationConfig,
        build_report,
        render_markdown,
        run_optimization,
    )
    from backend.app.analytics.optimization.types import OBJECTIVES
    from backend.app.analytics.replay import decisions as replay_decisions
    from backend.app.analytics.replay import replay as replay_mod
    from backend.app.analytics.simulation import events as events_mod
    from backend.app.analytics.simulation import scenarios as scenarios_mod
    from backend.app.analytics.simulation import targets as targets_mod
    from backend.app.analytics.simulation.types import (
        DEFAULT_SIMULATION_CONFIG,
        DisruptionEvent,
    )

    start, end = _parse_day(args.start_date), _parse_day(args.end_date)
    if start and end and start > end:
        print("Invalid dates: --start-date is after --end-date.")
        return 2
    if args.horizon_days is not None and not 1 <= args.horizon_days <= 180:
        print("Invalid --horizon-days: must be within [1, 180].")
        return 2
    if args.objective not in OBJECTIVES:
        print(f"Invalid --objective: expected one of {', '.join(OBJECTIVES)}.")
        return 2
    if args.objective == "cost_shortage_tradeoff" and (
        args.shortage_penalty is None or args.shortage_penalty <= 0
    ):
        print(
            "Invalid arguments: objective cost_shortage_tradeoff requires "
            "--shortage-penalty > 0."
        )
        return 2
    if args.budget is not None and args.budget <= 0:
        print("Invalid --budget: must be positive.")
        return 2
    if args.min_fulfillment is not None and not 0.0 <= args.min_fulfillment <= 1.0:
        print("Invalid --min-fulfillment: must lie in [0, 1].")
        return 2
    if args.time_limit <= 0:
        print("Invalid --time-limit: must be positive.")
        return 2

    scenario_payload: dict = {}
    if args.scenario_json:
        raw = args.scenario_json.strip()
        try:
            scenario_payload = (
                json.loads(raw) if raw.startswith("{")
                else json.loads(Path(raw).read_text(encoding="utf-8"))
            )
        except (ValueError, OSError) as exc:
            print(f"Invalid --scenario-json: {exc}")
            return 2
    event_payload = dict(scenario_payload.get("event") or {})
    try:
        if event_payload:
            event = DisruptionEvent(
                event_id=str(event_payload.get("event_id", "optimization-event")),
                event_type=str(event_payload.get("event_type", "")),
                name=str(event_payload.get("name", "")),
                description=str(event_payload.get("description", "")),
                start_date=str(event_payload.get("start_date", "")),
                duration_days=int(event_payload.get("duration_days", 14)),
                affected_suppliers=list(event_payload.get("affected_suppliers", []) or []),
                affected_products=list(event_payload.get("affected_products", []) or []),
                affected_warehouses=list(
                    event_payload.get("affected_warehouses", []) or []
                ),
                supply_reduction=float(event_payload.get("supply_reduction", 0.0)),
                lead_time_delay_days=int(event_payload.get("lead_time_delay_days", 0)),
                demand_multiplier=float(event_payload.get("demand_multiplier", 1.0)),
                warehouse_available=bool(event_payload.get("warehouse_available", True)),
                assumptions=list(event_payload.get("assumptions", []) or []),
            )
            events_mod.validate_event(event, check_targets=False)
        elif args.scenario:
            event = events_mod.apply_template(
                args.scenario,
                event_id=f"{args.scenario}-event",
                start_date="",
                **{
                    key: value for key, value in {
                        "duration_days": args.duration_days,
                        "supply_reduction": args.supply_reduction,
                        "lead_time_delay_days": args.lead_time_delay_days,
                        "demand_multiplier": args.demand_multiplier,
                    }.items() if value is not None
                },
            )
        else:
            print("Provide --scenario-json or --scenario (named template).")
            return 2
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"Invalid scenario definition: {exc}")
        return 2

    async with AsyncSessionLocal() as session:
        supplier_links = await suppliers_ds.load_suppliers(
            session, [args.supplier_id] if args.supplier_id else None
        )
        po_lines = await procurement_ds.load_purchase_orders(
            session, start, end, [args.supplier_id] if args.supplier_id else None
        )
        shipments = await procurement_ds.load_shipments(
            session, start, end, [args.supplier_id] if args.supplier_id else None
        )
        snapshots = await inventory_ds.load_snapshots(
            session, start, end,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        if snapshots.empty and po_lines.empty:
            print("Dataset is empty for the requested filters.")
            return 1
        latest_snap = pd.to_datetime(snapshots["snapshot_date"]).max().date() \
            if not snapshots.empty else None
        latest_po = pd.to_datetime(po_lines["order_date"]).max().date() \
            if not po_lines.empty else None
        candidates = [day for day in (end, latest_snap, latest_po) if day is not None]
        if not candidates:
            print("No dated records for the requested filters.")
            return 1
        analysis_date = min(candidates) if end else max(candidates)
        demand_frame = await demand_loader.load_demand(
            session, start, analysis_date,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
        persisted = await forecast_inputs.load_persisted_forecasts(
            session,
            [args.product_id] if args.product_id else None,
            [args.warehouse_id] if args.warehouse_id else None,
        )
    scenario_analysis_date = scenario_payload.get("analysis_date")
    analysis = date.fromisoformat(scenario_analysis_date) if scenario_analysis_date \
        else analysis_date
    horizon = args.horizon_days or int(scenario_payload.get("horizon_days", 0)) \
        or DEFAULT_SIMULATION_CONFIG.default_horizon_days
    simulation_count = args.simulation_count or int(
        scenario_payload.get("simulation_count", 1)
    )
    random_seed = args.random_seed if args.random_seed is not None else int(
        scenario_payload.get("random_seed", 42)
    )
    entities = targets_mod.resolve_explicit(
        supplier_ids=[args.supplier_id] if args.supplier_id else [],
        product_ids=[args.product_id] if args.product_id else [],
        warehouse_ids=[args.warehouse_id] if args.warehouse_id else [],
    )
    if args.supplier_id:
        entities.extend(
            targets_mod.resolve_supplier_products(args.supplier_id, supplier_links)
        )
    if not entities and scenario_payload.get("affected_entities"):
        entities = list(scenario_payload["affected_entities"])
    scenario_id = args.scenario_id or str(
        scenario_payload.get("scenario_id")
        or f"optimization-{event.event_type.lower()}"
    )
    try:
        scenario = scenarios_mod.build_scenario(
            scenario_id=scenario_id,
            event=event,
            analysis_date=analysis.isoformat(),
            horizon_days=horizon,
            affected_entities=entities,
            probability_mode=args.probability_mode,
            probability=args.probability,
            simulation_count=simulation_count,
            random_seed=random_seed,
            name=args.name or event.name,
        )
    except ValueError as exc:
        print(f"Invalid scenario: {exc}")
        return 2
    replay_id = replay_mod.resolve_replay_id(scenario)

    persisted_inputs = forecast_inputs.frame_to_inputs(persisted)
    series_keys = sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis
        ].iterrows()
    }) if not snapshots.empty else []
    wanted = {
        (str(item.get("product_id")), str(item.get("warehouse_id")))
        for item in entities if item.get("product_id") and item.get("warehouse_id")
    }
    if wanted:
        series_keys = sorted(set(series_keys) & wanted)
    if args.max_series is not None:
        series_keys = series_keys[: max(0, args.max_series)]
    missing = [key for key in series_keys if f"{key[0]}|{key[1]}" not in persisted_inputs]
    generated: dict[str, object] = {}
    if missing and not demand_frame.empty:
        missing_frame = demand_frame[
            demand_frame.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"])) in set(missing),
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = forecast_inputs.generate_inputs(
                missing_frame, analysis, AnalyticsConfig(
                    forecast_horizon=args.forecast_horizon, min_history=args.min_history
                ),
                season=args.season, max_series=args.max_series,
            )
    forecast_by_series: dict[str, object] = dict(persisted_inputs)
    forecast_by_series.update(generated)
    if wanted:
        forecast_by_series = {
            key: value for key, value in forecast_by_series.items()
            if tuple(key.split("|", 1)) in wanted
        }

    try:
        replay_run = replay_mod.run_replay(
            scenario, [replay_decisions.build_no_action(replay_id)],
            forecast_by_series, snapshots, shipments, po_lines, supplier_links,
            analysis, DEFAULT_SIMULATION_CONFIG, replay_id=replay_id,
        )
    except ValueError as exc:
        print(f"Cannot run replay context: {exc}")
        return 1
    try:
        baseline_entities = replay_mod.build_shared_baseline(
            scenario, forecast_by_series, snapshots, shipments, po_lines,
            supplier_links, analysis,
        )
    except ValueError as exc:
        print(f"Cannot build optimization scope: {exc}")
        return 1

    config = OptimizationConfig(
        objective=args.objective,
        shortage_penalty_per_unit=args.shortage_penalty,
        budget=args.budget,
        min_fulfillment=args.min_fulfillment,
        quantity_integrality=args.quantity_integrality,
        time_limit_seconds=args.time_limit,
    )
    try:
        run = run_optimization(
            replay_run, baseline_entities, supplier_links, config=config,
            forecast_by_series=forecast_by_series,
            product_id=args.product_id, warehouse_id=args.warehouse_id,
            supplier_id=args.supplier_id,
        )
    except ValueError as exc:
        print(f"Cannot run optimization: {exc}")
        return 1

    report_started = time_mod.perf_counter()
    report = build_report(run)
    markdown = render_markdown(report)
    report["optimization_run_metadata"]["timings_seconds"] = {
        **run["timings"],
        "reporting": round(time_mod.perf_counter() - report_started, 6),
    }
    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        print(f"Wrote {args.output_json}")
    if args.output_markdown:
        Path(args.output_markdown).write_text(markdown, encoding="utf-8")
        print(f"Wrote {args.output_markdown}")
    if not args.output_json and not args.output_markdown:
        _emit(report)
    print(f"Status: {report['feasibility_status']['status']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = argparse.ArgumentParser(description="Analyze the synthetic supply-chain dataset.")
    commands = parser.add_subparsers(dest="command", required=True)
    demand_cmd = commands.add_parser("demand", help="Demand summary and profiles.")
    _common(demand_cmd)
    demand_cmd.add_argument("--aggregation", default="day", choices=["day", "week", "month"])
    inventory_cmd = commands.add_parser("inventory", help="Inventory KPIs.")
    _common(inventory_cmd)
    procurement_cmd = commands.add_parser("procurement", help="Procurement KPIs.")
    _common(procurement_cmd)
    forecast_cmd = commands.add_parser("forecast", help="Demand forecast with selection.")
    _common(forecast_cmd)
    forecast_cmd.add_argument("--forecast-horizon", type=int, default=28)
    forecast_cmd.add_argument("--metric", default="mae",
                              choices=["mae", "rmse", "mape", "smape", "wape", "bias"])
    forecast_cmd.add_argument("--model", default=None,
                              help="Force one model (validated); default is routed selection.")
    forecast_cmd.add_argument("--min-history", type=int, default=90)
    forecast_cmd.add_argument("--validation-windows", type=int, default=None,
                              help="Number of walk-forward folds (overrides step).")
    forecast_cmd.add_argument("--season", type=int, default=7)
    forecast_cmd.add_argument("--include-ml", action="store_true",
                              help="Allow the gradient-boosting candidate in routing.")
    forecast_cmd.add_argument("--output", default=None, help="Write JSON evaluation to file.")
    forecast_cmd.add_argument("--persist", action="store_true",
                              help="Persist model version, run, and forecast rows.")
    forecast_report_cmd = commands.add_parser(
        "forecast-report", help="Multi-series forecasting evaluation report.")
    _common(forecast_report_cmd)
    forecast_report_cmd.add_argument("--forecast-horizon", type=int, default=28)
    forecast_report_cmd.add_argument("--metric", default="mae",
                                     choices=["mae", "rmse", "mape", "smape", "wape", "bias"])
    forecast_report_cmd.add_argument("--min-history", type=int, default=90)
    forecast_report_cmd.add_argument("--season", type=int, default=7)
    forecast_report_cmd.add_argument("--include-ml", action="store_true")
    forecast_report_cmd.add_argument("--max-series", type=int, default=None)
    forecast_report_cmd.add_argument("--output-json", default=None)
    forecast_report_cmd.add_argument("--output-markdown", default=None)
    report_cmd = commands.add_parser("report", help="Full analytics report.")
    _common(report_cmd)
    report_cmd.add_argument("--forecast-horizon", type=int, default=28)
    report_cmd.add_argument("--output-json", default=None)
    report_cmd.add_argument("--output-markdown", default=None)
    intel_cmd = commands.add_parser(
        "inventory-intelligence", help="Inventory intelligence signals.")
    _common(intel_cmd)
    intel_cmd.add_argument("--forecast-horizon", type=int, default=28)
    intel_cmd.add_argument("--min-history", type=int, default=90)
    intel_cmd.add_argument("--season", type=int, default=7)
    intel_cmd.add_argument("--max-series", type=int, default=None)
    intel_cmd.add_argument("--health", default=None,
                           choices=["STOCKOUT", "CRITICAL", "AT_RISK", "HEALTHY", "EXCESS", "UNKNOWN"],
                           help="Filter results to one health state.")
    intel_cmd.add_argument("--include-anomalies", action="store_true",
                           help="Include the anomaly section detail (always computed).")
    intel_cmd.add_argument("--output-json", default=None)
    intel_cmd.add_argument("--output-markdown", default=None)
    procurement_intel_cmd = commands.add_parser(
        "procurement-intelligence", help="Supplier & procurement intelligence.")
    _common(procurement_intel_cmd)
    procurement_intel_cmd.add_argument("--forecast-horizon", type=int, default=28)
    procurement_intel_cmd.add_argument("--min-history", type=int, default=90)
    procurement_intel_cmd.add_argument("--season", type=int, default=7)
    procurement_intel_cmd.add_argument("--max-series", type=int, default=None)
    procurement_intel_cmd.add_argument("--max-suppliers", type=int, default=None)
    procurement_intel_cmd.add_argument("--skip-open-orders", action="store_true",
                                       help="Exclude per-supplier open order lines.")
    procurement_intel_cmd.add_argument("--include-exposure", action="store_true",
                                       help="Include inbound coverage per series.")
    procurement_intel_cmd.add_argument("--include-concentration", action="store_true",
                                       help="Include volume and PO-count shares.")
    procurement_intel_cmd.add_argument("--output-json", default=None)
    procurement_intel_cmd.add_argument("--output-markdown", default=None)
    risk_cmd = commands.add_parser(
        "risk-intelligence", help="Supply-chain risk intelligence.")
    _common(risk_cmd)
    risk_cmd.add_argument("--forecast-horizon", type=int, default=28)
    risk_cmd.add_argument("--min-history", type=int, default=90)
    risk_cmd.add_argument("--season", type=int, default=7)
    risk_cmd.add_argument("--max-series", type=int, default=None)
    risk_cmd.add_argument("--max-suppliers", type=int, default=None)
    risk_cmd.add_argument("--severity", default=None,
                          help="Filter register to one severity.")
    risk_cmd.add_argument("--domain", default=None,
                          help="Filter register to one risk domain.")
    risk_cmd.add_argument("--include-evidence", action="store_true",
                          help="Include full register in stdout output.")
    risk_cmd.add_argument("--include-unknown", action="store_true", default=True,
                          help="Keep UNKNOWN records (default).")
    risk_cmd.add_argument("--exclude-unknown", action="store_true",
                          help="Drop UNKNOWN records from output.")
    risk_cmd.add_argument("--output-json", default=None)
    risk_cmd.add_argument("--output-markdown", default=None)
    sim_cmd = commands.add_parser(
        "disruption-simulation", help="Disruption scenario simulation.")
    _common(sim_cmd)
    sim_cmd.add_argument("--scenario", default=None,
                         help="Named template (SUPPLIER_OUTAGE, SUPPLIER_DELAY, "
                              "SHIPMENT_DELAY, SUPPLY_REDUCTION, WAREHOUSE_DISRUPTION, "
                              "DEMAND_SPIKE, COMBINED_DISRUPTION).")
    sim_cmd.add_argument("--scenario-id", default=None)
    sim_cmd.add_argument("--name", default=None)
    sim_cmd.add_argument("--event-type", default="SUPPLIER_DISRUPTION",
                         choices=["SUPPLIER_DISRUPTION", "SHIPMENT_DELAY",
                                  "LEAD_TIME_DELAY", "SUPPLY_REDUCTION",
                                  "WAREHOUSE_DISRUPTION", "DEMAND_SHOCK",
                                  "COMBINED_DISRUPTION"])
    sim_cmd.add_argument("--component", action="append", default=None,
                         help="COMBINED component as JSON (repeatable).")
    sim_cmd.add_argument("--risk-id", action="append", default=None,
                         help="Phase 7 risk record id for targeting.")
    sim_cmd.add_argument("--horizon-days", type=int, default=None)
    sim_cmd.add_argument("--forecast-horizon", type=int, default=28)
    sim_cmd.add_argument("--min-history", type=int, default=90)
    sim_cmd.add_argument("--season", type=int, default=7)
    sim_cmd.add_argument("--max-series", type=int, default=None)
    sim_cmd.add_argument("--duration-days", type=int, default=None)
    sim_cmd.add_argument("--supply-reduction", type=float, default=None)
    sim_cmd.add_argument("--lead-time-delay-days", type=int, default=None)
    sim_cmd.add_argument("--demand-multiplier", type=float, default=None)
    sim_cmd.add_argument("--probability-mode", default="deterministic",
                         choices=["deterministic", "explicit", "empirical"])
    sim_cmd.add_argument("--probability", type=float, default=None)
    sim_cmd.add_argument("--duration-min", type=float, default=None)
    sim_cmd.add_argument("--duration-mode", type=float, default=None)
    sim_cmd.add_argument("--duration-max", type=float, default=None)
    sim_cmd.add_argument("--reduction-min", type=float, default=None)
    sim_cmd.add_argument("--reduction-max", type=float, default=None)
    sim_cmd.add_argument("--simulation-count", type=int, default=1)
    sim_cmd.add_argument("--random-seed", type=int, default=42)
    sim_cmd.add_argument("--output-json", default=None)
    sim_cmd.add_argument("--output-markdown", default=None)
    replay_cmd = commands.add_parser(
        "decision-replay",
        help="Decision Replay Lab: factual decision comparison (Phase 9).")
    _common(replay_cmd)
    replay_cmd.add_argument("--scenario-id", default=None)
    replay_cmd.add_argument("--scenario", default=None,
                            help="Named Phase 8 template (SUPPLIER_OUTAGE, ...).")
    replay_cmd.add_argument("--scenario-json", default=None,
                            help="Inline scenario JSON or path to a scenario JSON file.")
    replay_cmd.add_argument("--name", default=None)
    replay_cmd.add_argument("--decision", action="append", default=None,
                            help="Decision definition as JSON (repeatable).")
    replay_cmd.add_argument("--decision-file", action="append", default=None,
                            help="Path to a JSON decision file (repeatable).")
    replay_cmd.add_argument("--horizon-days", type=int, default=None)
    replay_cmd.add_argument("--forecast-horizon", type=int, default=28)
    replay_cmd.add_argument("--min-history", type=int, default=90)
    replay_cmd.add_argument("--season", type=int, default=7)
    replay_cmd.add_argument("--max-series", type=int, default=None)
    replay_cmd.add_argument("--simulation-count", type=int, default=None)
    replay_cmd.add_argument("--random-seed", type=int, default=None)
    replay_cmd.add_argument("--probability-mode", default="deterministic",
                            choices=["deterministic", "explicit", "empirical"])
    replay_cmd.add_argument("--probability", type=float, default=None)
    replay_cmd.add_argument("--duration-days", type=int, default=None)
    replay_cmd.add_argument("--supply-reduction", type=float, default=None)
    replay_cmd.add_argument("--lead-time-delay-days", type=int, default=None)
    replay_cmd.add_argument("--demand-multiplier", type=float, default=None)
    replay_cmd.add_argument("--output-json", default=None)
    replay_cmd.add_argument("--output-markdown", default=None)
    opt_cmd = commands.add_parser(
        "optimization",
        help="Optimization Engine: disruption-aware procurement planning (Phase 10).")
    _common(opt_cmd)
    opt_cmd.add_argument("--scenario-id", default=None)
    opt_cmd.add_argument("--scenario", default=None,
                         help="Named Phase 8 template (SUPPLIER_OUTAGE, ...).")
    opt_cmd.add_argument("--scenario-json", default=None,
                         help="Inline scenario JSON or path to a scenario JSON file.")
    opt_cmd.add_argument("--name", default=None)
    opt_cmd.add_argument("--objective", default="minimize_total_cost",
                         choices=["minimize_total_cost", "minimize_shortage",
                                  "cost_shortage_tradeoff",
                                  "maximize_service_fulfillment"],
                         help="Scalar objective (default: minimize_total_cost).")
    opt_cmd.add_argument("--shortage-penalty", type=float, default=None,
                         help="Penalty per unsatisfied unit (required for the "
                              "cost_shortage_tradeoff objective).")
    opt_cmd.add_argument("--budget", type=float, default=None,
                         help="Optional hard procurement budget cap.")
    opt_cmd.add_argument("--min-fulfillment", type=float, default=None,
                         help="Optional service-level floor in [0, 1].")
    opt_cmd.add_argument("--quantity-integrality", default="integer",
                         choices=["integer", "continuous"],
                         help="Order quantities must be whole units or may be fractional.")
    opt_cmd.add_argument("--time-limit", type=float, default=30.0,
                         help="Solver time limit in seconds (default: 30).")
    opt_cmd.add_argument("--horizon-days", type=int, default=None)
    opt_cmd.add_argument("--forecast-horizon", type=int, default=28)
    opt_cmd.add_argument("--min-history", type=int, default=90)
    opt_cmd.add_argument("--season", type=int, default=7)
    opt_cmd.add_argument("--max-series", type=int, default=None)
    opt_cmd.add_argument("--simulation-count", type=int, default=None)
    opt_cmd.add_argument("--random-seed", type=int, default=None)
    opt_cmd.add_argument("--probability-mode", default="deterministic",
                         choices=["deterministic", "explicit", "empirical"])
    opt_cmd.add_argument("--probability", type=float, default=None)
    opt_cmd.add_argument("--duration-days", type=int, default=None)
    opt_cmd.add_argument("--supply-reduction", type=float, default=None)
    opt_cmd.add_argument("--lead-time-delay-days", type=int, default=None)
    opt_cmd.add_argument("--demand-multiplier", type=float, default=None)
    opt_cmd.add_argument("--output-json", default=None)
    opt_cmd.add_argument("--output-markdown", default=None)
    args = parser.parse_args(argv)

    async def _dispatch() -> int:
        if not await _check_connection():
            print("SupplySense Nexus database is unavailable.")
            print("Verify PostgreSQL is running and DATABASE_URL is configured.")
            return 2
        if args.command == "demand":
            return await _cmd_demand(args)
        if args.command == "inventory":
            return await _cmd_inventory(args)
        if args.command == "procurement":
            return await _cmd_procurement(args)
        if args.command == "forecast":
            return await _cmd_forecast(args)
        if args.command == "forecast-report":
            return await _cmd_forecast_report(args)
        if args.command == "report":
            return await _cmd_report(args)
        if args.command == "inventory-intelligence":
            return await _cmd_inventory_intelligence(args)
        if args.command == "procurement-intelligence":
            return await _cmd_procurement_intelligence(args)
        if args.command == "risk-intelligence":
            return await _cmd_risk_intelligence(args)
        if args.command == "disruption-simulation":
            return await _cmd_disruption_simulation(args)
        if args.command == "decision-replay":
            return await _cmd_decision_replay(args)
        if args.command == "optimization":
            return await _cmd_optimization(args)
        return 2

    try:
        return run_async(_dispatch())
    finally:
        run_async(dispose_engine())


if __name__ == "__main__":
    raise SystemExit(main())

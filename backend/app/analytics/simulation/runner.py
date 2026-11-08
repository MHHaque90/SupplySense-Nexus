"""Scenario execution orchestration (Phase 8).

Resolves target series, builds each baseline ONCE, runs baseline and
disrupted passes (deterministic or Monte Carlo), and aggregates
outcomes with traceability. Pure orchestration over the engine and
outcome modules; no database access here.
"""

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.simulation import (
    comparison as comparison_mod,
)
from backend.app.analytics.simulation import (
    monte_carlo as mc,
)
from backend.app.analytics.simulation import (
    outcomes as outcomes_mod,
)
from backend.app.analytics.simulation import (
    simulation as sim_mod,
)
from backend.app.analytics.simulation import (
    traceability as trace_mod,
)
from backend.app.analytics.simulation.baseline import build_baseline_series
from backend.app.analytics.simulation.types import (
    ScenarioOutcome,
    SimulationConfig,
    SimulationScenario,
)


def resolve_series(
    targets: list[dict[str, Any]],
    snapshots: pd.DataFrame,
    supplier_links: pd.DataFrame,
) -> list[tuple[str, str]]:
    """Resolve target entities to product/warehouse series keys."""
    stocked: dict[str, set[str]] = {}
    if not snapshots.empty:
        for product_id, group in snapshots.groupby("product_id"):
            stocked[str(product_id)] = {str(value) for value in group["warehouse_id"].tolist()}
    product_suppliers: dict[str, set[str]] = {}
    if not supplier_links.empty:
        for product_id, group in supplier_links.groupby("product_id"):
            product_suppliers[str(product_id)] = {str(value) for value in group["supplier_id"].tolist()}
    keys: set[tuple[str, str]] = set()
    for target in targets:
        kind = target.get("entity_type")
        if kind == "product" and "warehouse_id" in target:
            keys.add((str(target["product_id"]), str(target["warehouse_id"])))
        elif kind == "product":
            for warehouse in sorted(stocked.get(str(target["product_id"]), set())):
                keys.add((str(target["product_id"]), warehouse))
        elif kind == "warehouse":
            for product, warehouses in stocked.items():
                if str(target["warehouse_id"]) in warehouses:
                    keys.add((product, str(target["warehouse_id"])))
        elif kind == "supplier":
            for product, suppliers in product_suppliers.items():
                if str(target["supplier_id"]) in suppliers:
                    for warehouse in sorted(stocked.get(product, set())):
                        keys.add((product, warehouse))
        elif kind == "supplier_product":
            for warehouse in sorted(stocked.get(str(target["product_id"]), set())):
                keys.add((str(target["product_id"]), warehouse))
    return sorted(keys)


def _on_hand(
    snapshots: pd.DataFrame, product_id: str, warehouse_id: str, analysis_date: date
) -> float | None:
    frame = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date)
    ].sort_values("snapshot_date")
    if frame.empty:
        return None
    return float(frame.iloc[-1]["on_hand"])


def run_scenario(
    scenario: SimulationScenario,
    forecast_by_series: dict[str, ForecastInput],
    snapshots: pd.DataFrame,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    supplier_links: pd.DataFrame,
    analysis_date: date,
    config: SimulationConfig,
) -> dict[str, Any]:
    """Execute baseline once plus disrupted runs for every target series."""
    horizon = scenario.horizon_days
    horizon_end = analysis_date.fromordinal(analysis_date.toordinal() + horizon)
    targets = scenario.affected_entities
    series_keys = resolve_series(targets, snapshots, supplier_links)
    if not series_keys and targets:
        # Explicit product+warehouse pairs resolve even without snapshots.
        for target in targets:
            if target.get("entity_type") == "product" and target.get("warehouse_id"):
                series_keys.append((str(target["product_id"]), str(target["warehouse_id"])))
        series_keys = sorted(set(series_keys))
    rng = mc.make_generator(scenario.random_seed)
    sampled = mc.sample_parameters(
        list(scenario.event.distributions) if scenario.event else [],
        rng, scenario.simulation_count,
    )
    if not series_keys:
        raise ValueError("No product/warehouse series resolved for the scenario targets.")
    event = scenario.event
    per_entity: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    affected_suppliers: set[str] = set()
    affected_pairs = 0
    for product_id, warehouse_id in series_keys:
        key = f"{product_id}|{warehouse_id}"
        forecast = forecast_by_series.get(key)
        if forecast is None or forecast.missing:
            continue
        on_hand = _on_hand(snapshots, product_id, warehouse_id, analysis_date)
        if on_hand is None:
            continue
        demand_point = [float(v) for v in forecast.point]
        demand_lower = [float(v) for v in forecast.lower]
        demand_upper = [float(v) for v in forecast.upper]
        extension_note: str | None = None
        if len(demand_point) < horizon:
            # Transparently extend short forecasts by repeating the last
            # value so every series covers the scenario horizon.
            shortfall = horizon - len(demand_point)
            last_point = demand_point[-1] if demand_point else 0.0
            last_lower = demand_lower[-1] if demand_lower else 0.0
            last_upper = demand_upper[-1] if demand_upper else 0.0
            demand_point = demand_point + [last_point] * shortfall
            demand_lower = demand_lower + [last_lower] * shortfall
            demand_upper = demand_upper + [last_upper] * shortfall
            extension_note = (
                "Forecast shorter than the scenario horizon; extended by "
                "repeating the last value (scenario assumption)."
            )
        demand_point = demand_point[:horizon]
        demand_lower = demand_lower[:horizon]
        demand_upper = demand_upper[:horizon]
        state = build_baseline_series(
            product_id, warehouse_id, on_hand, demand_point, demand_lower,
            demand_upper, analysis_date, horizon, shipments, po_lines,
            analysis_date,
            {"model_name": forecast.model_name, "origin": forecast.origin,
             "horizon": forecast.horizon},
        )
        schedule = sim_mod.build_inbound_schedule(
            product_id, shipments, po_lines, analysis_date, horizon_end,
            state["forecast_dates"],
        )
        base_run = sim_mod.run_baseline_once(on_hand, demand_point, schedule, horizon)
        base_summary = _summarize_run(base_run, horizon)
        suppliers_here = sorted({str(item["supplier_id"]) for item in schedule})
        affected_suppliers.update(s for s in suppliers_here if s)
        targets_hit = (
            [s for s in suppliers_here if s in set(event.affected_suppliers)]
            if event and event.affected_suppliers else []
        )
        affected_pairs += 1 if targets_hit else 0
        iteration_results = []
        affected_results = []
        for iteration in range(scenario.simulation_count):
            params = {name: float(values[iteration]) for name, values in sampled.items()}
            run = sim_mod.run_entity_once(
                on_hand, demand_point, schedule, horizon, event, params
            )
            iteration_results.append(_summarize_run(run, horizon))
            affected_results.append(_account_effects(
                schedule, event, params, horizon
            ))
        per_entity.append({
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "baseline": base_summary,
            "iterations": iteration_results,
            "affected": affected_results,
            "forecast_meta": state["forecast_meta"],
            "schedule": schedule,
        })
        traces.append(trace_mod.build_trace(
            scenario, product_id, warehouse_id, suppliers_here,
            state["forecast_meta"], on_hand,
            sorted({str(item["po_id"]) for item in schedule}),
        ))
        if extension_note:
            traces[-1]["notes"] = [extension_note]
    baseline_outcome, scenario_outcome = _aggregate_all(
        per_entity, horizon, scenario, config, affected_suppliers, affected_pairs,
    )
    deltas = comparison_mod.compare(baseline_outcome, scenario_outcome)
    return {
        "per_entity": per_entity,
        "baseline": baseline_outcome,
        "scenario": scenario_outcome,
        "deltas": deltas,
        "traces": traces,
    }


def _account_effects(schedule, event, params, horizon_days):
    """Mirror the engine's effect dispatch for supply accounting.

    Returns (delayed_qty, unavailable_qty, affected_count) for one
    iteration using the same supply_effects calls as the engine path.
    """
    from backend.app.analytics.simulation import supply_effects as supply_mod

    arrivals = np.zeros(horizon_days)
    suppliers: list[str | None] = [None] * horizon_days
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon_days:
            arrivals[offset] += float(entry["quantity"])
            suppliers[offset] = str(entry.get("supplier_id"))
    targets = list(event.affected_suppliers) if event else []
    duration = params.get("duration_days", event.duration_days if event else 0)
    duration = int(min(duration, horizon_days))
    delayed, unavailable, affected = 0.0, 0.0, 0
    parts = (
        list(event.components)
        if event and event.event_type == "COMBINED_DISRUPTION" and event.components
        else ([event] if event else [])
    )
    for part in parts:
        part_type = part.event_type
        part_targets = list(part.affected_suppliers) or targets
        if part_type in ("SUPPLIER_DISRUPTION", "COMBINED_DISRUPTION"):
            reduction = params.get("supply_reduction", part.supply_reduction)
            _, info = supply_mod.apply_supplier_disruption(
                arrivals, suppliers, part_targets, reduction, 0, duration)
            unavailable += info["unavailable_inbound_quantity"]
        if part_type == "SUPPLY_REDUCTION":
            reduction = params.get("supply_reduction", part.supply_reduction)
            _, info = supply_mod.apply_supply_reduction(arrivals, reduction, 0, duration)
            unavailable += info["unavailable_inbound_quantity"]
        if part_type in ("SHIPMENT_DELAY", "LEAD_TIME_DELAY", "COMBINED_DISRUPTION"):
            delay = int(params.get("lead_time_delay_days", part.lead_time_delay_days))
            _, info = supply_mod.apply_arrival_delay(arrivals, delay, 0, duration)
            delayed += info["delayed_inbound_quantity"]
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < duration and str(entry.get("supplier_id")) in set(targets):
            affected += 1
            break
    return delayed, unavailable, affected


def _summarize_run(run: dict[str, np.ndarray], horizon: int) -> dict[str, object]:
    """Reduce one engine run to aggregation-ready scalars."""
    ending = np.asarray(run["ending"], dtype=float)
    unmet = np.asarray(run["unmet"], dtype=float)
    stockout = np.asarray(run["stockout_flag"], dtype=bool)
    first = inventory_first(stockout)
    return {
        "any_stockout": bool(stockout.any()),
        "stockout_days": float(stockout.sum()),
        "min_inventory": float(ending.min()) if horizon else 0.0,
        "ending_inventory": float(ending[-1]) if horizon else 0.0,
        "unmet_demand": float(unmet.sum()),
        "depleted": bool(ending[-1] <= 0) if horizon else False,
        "service_exposed": bool(unmet.sum() > 0),
        "stockout_by_7": bool(stockout[:7].any()) if horizon >= 7 else False,
        "stockout_by_14": bool(stockout[:14].any()) if horizon >= 14 else False,
        "stockout_by_28": bool(stockout[:28].any()) if horizon >= 28 else False,
        "first_stockout_date": None,  # resolved with calendar by the caller
        "first_stockout_day": first,
    }


def inventory_first(stockout: np.ndarray) -> int | None:
    """Return the first stockout day index or None."""
    hits = np.flatnonzero(stockout)
    return int(hits[0]) if len(hits) else None


def _aggregate_all(
    per_entity: list[dict[str, Any]],
    horizon: int,
    scenario: SimulationScenario,
    config: SimulationConfig,
    affected_suppliers: set[str],
    affected_pairs: int,
) -> tuple[ScenarioOutcome, ScenarioOutcome]:
    """Aggregate baseline and scenario outcomes across entities."""
    from datetime import timedelta

    origin = date.fromisoformat(scenario.analysis_date)
    calendar = [(origin + timedelta(days=step)).isoformat() for step in range(1, horizon + 1)]

    def _collect(label: str) -> ScenarioOutcome:
        products, warehouses, inbound_total, delayed_total, unavailable_total = set(), set(), 0, 0.0, 0.0
        flat: list[dict[str, object]] = []
        for entity in per_entity:
            products.add(entity["product_id"])
            warehouses.add(entity["warehouse_id"])
            if label == "baseline":
                runs = [entity["baseline"]]
            else:
                runs = entity["iterations"]
            for run in runs:
                item = dict(run)
                day = run.get("first_stockout_day")
                item["first_stockout_date"] = calendar[day] if isinstance(day, int) else None
                flat.append(item)
        # Supply-side totals come from schedules (scenario runs share them).
        return outcomes_mod.aggregate(
            flat, label, horizon, sorted(products), sorted(warehouses),
            sorted(affected_suppliers), affected_pairs, inbound_total,
            delayed_total, unavailable_total, config,
        )

    baseline_outcome = _collect("baseline")
    scenario_outcome = _collect("scenario")
    # Supply quantities: mean over iterations of per-iteration accounting.
    delayed_vals: list[float] = []
    unavailable_vals: list[float] = []
    inbound_count = 0
    suppliers: set[str] = set()
    for entity in per_entity:
        for item in entity["schedule"]:
            inbound_count += 1
            suppliers.add(str(item["supplier_id"]))
        for delayed, unavailable, _ in entity.get("affected", []):
            delayed_vals.append(delayed)
            unavailable_vals.append(unavailable)
    if delayed_vals:
        scenario_outcome.delayed_inbound_quantity = float(np.mean(delayed_vals))
    if unavailable_vals:
        scenario_outcome.unavailable_inbound_quantity = float(np.mean(unavailable_vals))
    scenario_outcome.affected_inbound_count = inbound_count
    scenario_outcome.affected_supplier_count = len(suppliers)
    return baseline_outcome, scenario_outcome

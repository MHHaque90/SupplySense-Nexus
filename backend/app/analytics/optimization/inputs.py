"""Phase 9 -> Phase 10 input adapter.

Documented input contract (also recorded in ``docs/optimization-engine.md``):

- ``replay_run``: the public dict returned by ``replay.run_replay(...)`` run
  with at least the ``NO_ACTION`` control arm. Required keys: ``replay_id``,
  ``scenario_id``, ``scenario``, ``scenario_fingerprint``, ``baseline_ref``,
  ``baseline``, ``results``, ``uncertainty``, ``sample_fingerprint``,
  ``synthetic``. Malformed runs raise ``ValueError`` with explicit messages.
- ``entities``: the public list returned by ``replay.build_shared_baseline(...)``.
- ``supplier_links``: the supplier-link frame (``supplier_id``, ``product_id``,
  ``unit_cost``, ``lead_time_days``, ``min_order_qty``, ``capacity_units``).
- ``forecast_by_series``: optional Phase 4 forecast inputs keyed
  ``"product|warehouse"`` for richer provenance references.

Derived here (documented derivations, no hidden inputs):

1. Event-adjusted demand/inbound/availability mirror ``run_entity_once``
   dispatch exactly, using the scenario's declared POINT parameters
   (Monte Carlo samples are never resampled — optimization is deterministic).
2. A new order from supplier ``s`` with lead time ``L`` arrives at horizon day
   ``L - 1`` (day 0 = analysis_date + 1, matching ``build_inbound_schedule``),
   then passes through the same scenario supply effects as existing inbound.
   Orders with ``L <= 0`` or ``L > horizon`` or fully eliminated by the event
   are excluded with a recorded reason.
3. The deterministic current-plan reference re-evaluates each entity with
   ``inventory_engine.run_days`` (event-aware point accounting).
4. Scenario comparison carries the Phase 9 factual baseline-vs-no-action
   deltas; the optimized plan is NOT re-simulated (documented limitation).

All outputs are SYNTHETIC / simulated planning data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.optimization.types import OptimizationConfig, Provenance
from backend.app.analytics.simulation import (
    demand_effects,
    inventory_engine,
    supply_effects,
)

_NO_ACTION = "NO_ACTION"

_REQUIRED_REPLAY_KEYS = (
    "replay_id",
    "scenario_id",
    "scenario",
    "scenario_fingerprint",
    "baseline_ref",
    "baseline",
    "results",
    "uncertainty",
    "sample_fingerprint",
)

_REQUIRED_ENTITY_KEYS = (
    "product_id",
    "warehouse_id",
    "on_hand",
    "demand_point",
    "demand_lower",
    "demand_upper",
    "schedule",
    "forecast_meta",
)

_REQUIRED_LINK_COLUMNS = (
    "supplier_id",
    "product_id",
    "unit_cost",
    "lead_time_days",
    "min_order_qty",
    "capacity_units",
)

ASSUMPTIONS = (
    "Order arrivals are placed at analysis_date + lead_time_days (horizon day "
    "lead_time_days - 1) and pass through the same scenario event mechanics "
    "as existing inbound.",
    "Event effects use the scenario's declared point parameters; Monte Carlo "
    "samples from the replay run are not resampled (deterministic optimization).",
    "The deterministic current-plan reference re-evaluates each entity with "
    "the Phase 8 daily engine (point accounting), not Monte Carlo samples.",
    "Orders that arrive after the horizon are out of scope and are excluded "
    "with a recorded reason.",
)


@dataclass(frozen=True)
class EntityRequirement:
    """One scoped product/warehouse requirement with event-adjusted inputs."""

    product_id: str
    warehouse_id: str
    demand: tuple[float, ...]
    demand_lower: tuple[float, ...]
    demand_upper: tuple[float, ...]
    on_hand: float
    existing_inbound: tuple[float, ...]
    available: tuple[bool, ...]
    baseline_unmet: float
    baseline_served: float
    forecast_meta: dict[str, Any]


@dataclass(frozen=True)
class SupplierOffer:
    """One eligible supplier-product link inside the scoped horizon."""

    supplier_id: str
    product_id: str
    unit_cost: float | None
    lead_time_days: int | None
    min_order_qty: float
    capacity_units: float | None
    arrival_day: int
    arrival_factor: float
    warehouses: tuple[str, ...]


@dataclass(frozen=True)
class OptimizationInputs:
    """Everything the MILP builder and comparison layers consume."""

    analysis_date: str
    horizon_days: int
    scenario: dict[str, Any]
    event: dict[str, Any] | None
    entities: tuple[EntityRequirement, ...]
    offers: tuple[SupplierOffer, ...]
    excluded_offers: tuple[dict[str, Any], ...]
    provenance: Provenance
    uncertainty: dict[str, Any]
    baseline_outcome: dict[str, Any]
    no_action_outcome: dict[str, Any] | None
    scenario_impact: dict[str, Any] | None
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    config: OptimizationConfig = field(default_factory=OptimizationConfig)
    forecast_references: tuple[dict[str, Any], ...] = ()


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    """Raise a ValueError naming exactly which keys are missing."""
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ValueError(f"{label} missing required keys: {', '.join(missing)}.")


def _window(event: dict[str, Any] | None, horizon_days: int) -> tuple[int, int]:
    """Mirror ``simulation.simulation._window``: start 0, clipped duration."""
    if not event:
        return 0, 0
    duration = min(int(event.get("duration_days", 0)), horizon_days)
    return 0, duration


def _event_parts(
    event: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Flatten a scenario event into dispatch parts (COMBINED components)."""
    if not event:
        return []
    if event.get("event_type") == "COMBINED_DISRUPTION" and event.get("components"):
        return list(event["components"])
    return [event]


def _arrivals_from_schedule(
    schedule: list[dict[str, Any]], horizon_days: int,
) -> tuple[np.ndarray, list[str | None]]:
    """Build the daily arrivals array plus supplier attribution."""
    arrivals = np.zeros(horizon_days, dtype=float)
    suppliers: list[str | None] = [None] * horizon_days
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon_days:
            arrivals[offset] += float(entry["quantity"])
            suppliers[offset] = str(entry.get("supplier_id")) or suppliers[offset]
    return arrivals, suppliers


def _apply_supply_parts(
    arrivals: np.ndarray,
    suppliers: list[str | None],
    event: dict[str, Any] | None,
    horizon_days: int,
) -> np.ndarray:
    """Apply only supply-side dispatch (mirror of ``run_entity_once``)."""
    if not event:
        return arrivals
    start, duration = _window(event, horizon_days)
    parent_targets = [str(value) for value in event.get("affected_suppliers", [])]
    adjusted = arrivals
    for part in _event_parts(event):
        part_type = part.get("event_type")
        part_targets = [str(value) for value in part.get("affected_suppliers", [])]
        part_targets = part_targets or parent_targets
        if part_type in ("SUPPLIER_DISRUPTION", "COMBINED_DISRUPTION"):
            adjusted, _ = supply_effects.apply_supplier_disruption(
                adjusted, suppliers, part_targets,
                float(part.get("supply_reduction", 0.0)), start, duration,
            )
        if part_type == "SUPPLY_REDUCTION":
            adjusted, _ = supply_effects.apply_supply_reduction(
                adjusted, float(part.get("supply_reduction", 0.0)), start, duration,
            )
        if part_type in ("SHIPMENT_DELAY", "LEAD_TIME_DELAY", "COMBINED_DISRUPTION"):
            delay = int(part.get("lead_time_delay_days", 0))
            adjusted, _ = supply_effects.apply_arrival_delay(
                adjusted, delay, start, duration,
            )
    return adjusted


def _apply_event(
    point: list[float],
    lower: list[float],
    upper: list[float],
    arrivals: np.ndarray,
    suppliers: list[str | None],
    event: dict[str, Any] | None,
    horizon_days: int,
) -> tuple[list[float], list[float], list[float], np.ndarray, np.ndarray]:
    """Apply the full event dispatch exactly as ``run_entity_once`` does."""
    available = np.ones(horizon_days, dtype=bool)
    demand_point = list(point)
    demand_lower = list(lower)
    demand_upper = list(upper)
    if not event:
        return demand_point, demand_lower, demand_upper, arrivals, available
    start, duration = _window(event, horizon_days)
    window_end = start + duration if duration else horizon_days
    for part in _event_parts(event):
        part_type = part.get("event_type")
        if part_type == "DEMAND_SHOCK":
            multiplier = float(part.get("demand_multiplier", 1.0))
            demand_point, demand_lower, demand_upper = (
                demand_effects.apply_demand_multiplier(
                    demand_point, demand_lower, demand_upper,
                    multiplier, start, window_end,
                )
            )
        if part_type == "WAREHOUSE_DISRUPTION":
            available[start:window_end] = False
    adjusted_arrivals = _apply_supply_parts(arrivals, suppliers, event, horizon_days)
    return demand_point, demand_lower, demand_upper, adjusted_arrivals, available


def _order_arrival(
    lead_time_days: int, supplier_id: str, event: dict[str, Any] | None,
    horizon_days: int,
) -> tuple[int, float] | None:
    """Effective in-horizon arrival (day, factor) for a new order, or None."""
    if lead_time_days <= 0:
        return None
    offset = lead_time_days - 1
    if offset >= horizon_days:
        return None
    unit = np.zeros(horizon_days, dtype=float)
    unit[offset] = 1.0
    suppliers: list[str | None] = [None] * horizon_days
    suppliers[offset] = supplier_id
    adjusted = _apply_supply_parts(unit, suppliers, event, horizon_days)
    hits = np.flatnonzero(np.abs(adjusted) > 1e-12)
    if not len(hits):
        return None
    day = int(hits[0])
    factor = float(adjusted[day])
    return day, factor


def _scalar(frame: pd.DataFrame, column: str) -> float | None:
    """Coerce one numeric cell to float, mapping missing values to None."""
    value = pd.to_numeric(pd.Series([frame[column]]), errors="coerce").iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def _forecast_references(
    entities: tuple[EntityRequirement, ...],
    forecast_by_series: dict[str, ForecastInput] | None,
) -> tuple[dict[str, Any], ...]:
    """Collect per-entity forecast provenance references."""
    references: list[dict[str, Any]] = []
    for entity in entities:
        key = f"{entity.product_id}|{entity.warehouse_id}"
        forecast = (forecast_by_series or {}).get(key)
        if forecast is not None:
            references.append({
                "product_id": entity.product_id,
                "warehouse_id": entity.warehouse_id,
                "model_name": forecast.model_name,
                "model_version": forecast.model_version,
                "confidence_level": forecast.confidence_level,
                "validation_metric": forecast.validation_metric,
                "validation_score": forecast.validation_score,
                "origin": forecast.origin,
                "source": forecast.source,
            })
        else:
            meta = dict(entity.forecast_meta)
            references.append({
                "product_id": entity.product_id,
                "warehouse_id": entity.warehouse_id,
                "model_name": str(meta.get("model_name", "")),
                "origin": str(meta.get("origin", "")),
                "source": "entity_forecast_meta",
            })
    return tuple(references)


def _no_action_outcome(
    results: list[Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Extract the NO_ACTION arm outcome and its recorded baseline deltas."""
    outcome: dict[str, Any] | None = None
    deltas: dict[str, Any] | None = None
    for result in results:
        if getattr(result, "decision_type", None) == _NO_ACTION:
            outcome = dict(getattr(result, "outcome", {}) or {})
            deltas = dict(getattr(result, "baseline_delta", {}) or {})
            break
    return outcome, deltas


def build_optimization_inputs(
    replay_run: dict[str, Any],
    entities: list[dict[str, Any]],
    supplier_links: pd.DataFrame,
    config: OptimizationConfig | None = None,
    forecast_by_series: dict[str, ForecastInput] | None = None,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    supplier_id: str | None = None,
) -> OptimizationInputs:
    """Build the Phase 10 input bundle from public Phase 9 outputs.

    Raises ``ValueError`` for malformed replay runs, malformed entities, or
    missing supplier-link columns. Empty scope is valid here; the
    orchestration layer converts it into a ``NO_DATA`` result.
    """
    config = config or OptimizationConfig()
    _require_keys(replay_run, _REQUIRED_REPLAY_KEYS, "replay_run")
    scenario = dict(replay_run["scenario"])
    _require_keys(scenario, ("scenario_id", "analysis_date", "horizon_days"), "scenario")
    horizon_days = int(scenario["horizon_days"])
    if horizon_days <= 0:
        raise ValueError("scenario horizon_days must be positive.")
    analysis_date = str(scenario["analysis_date"])
    event = scenario.get("event")
    missing_columns = [
        column for column in _REQUIRED_LINK_COLUMNS if column not in supplier_links.columns
    ]
    if missing_columns:
        raise ValueError(
            f"supplier_links missing required columns: {', '.join(missing_columns)}."
        )

    warnings: list[str] = []
    scoped: list[dict[str, Any]] = []
    for entity in entities:
        _require_keys(entity, _REQUIRED_ENTITY_KEYS, "entity")
        if product_id and str(entity["product_id"]) != product_id:
            continue
        if warehouse_id and str(entity["warehouse_id"]) != warehouse_id:
            continue
        scoped.append(entity)

    entity_requirements: list[EntityRequirement] = []
    for entity in scoped:
        current_product = str(entity["product_id"])
        current_warehouse = str(entity["warehouse_id"])
        arrivals, suppliers = _arrivals_from_schedule(
            list(entity["schedule"]), horizon_days
        )
        point = [float(value) for value in list(entity["demand_point"])][:horizon_days]
        lower = [float(value) for value in list(entity["demand_lower"])][:horizon_days]
        upper = [float(value) for value in list(entity["demand_upper"])][:horizon_days]
        for series_name, series in (("point", point), ("lower", lower), ("upper", upper)):
            if len(series) != horizon_days:
                raise ValueError(
                    f"entity {current_product}|{current_warehouse} demand_{series_name} "
                    f"length {len(series)} does not match horizon {horizon_days}."
                )
        adj_point, adj_lower, adj_upper, adj_arrivals, available = _apply_event(
            point, lower, upper, arrivals, suppliers, event, horizon_days
        )
        on_hand = float(entity["on_hand"])
        baseline_run = inventory_engine.run_days(
            on_hand, np.asarray(adj_point, dtype=float), adj_arrivals, available,
        )
        unmet = np.asarray(baseline_run["unmet"], dtype=float)
        demand_arr = np.asarray(adj_point, dtype=float)
        entity_requirements.append(EntityRequirement(
            product_id=current_product,
            warehouse_id=current_warehouse,
            demand=tuple(float(value) for value in demand_arr),
            demand_lower=tuple(float(value) for value in adj_lower),
            demand_upper=tuple(float(value) for value in adj_upper),
            on_hand=on_hand,
            existing_inbound=tuple(float(value) for value in adj_arrivals),
            available=tuple(bool(value) for value in available),
            baseline_unmet=float(np.sum(unmet)),
            baseline_served=float(np.sum(demand_arr) - np.sum(unmet)),
            forecast_meta=dict(entity.get("forecast_meta", {})),
        ))

    products_in_scope = {item.product_id for item in entity_requirements}
    warehouses_by_product: dict[str, list[str]] = {}
    for item in entity_requirements:
        warehouses_by_product.setdefault(item.product_id, []).append(item.warehouse_id)

    offers: list[SupplierOffer] = []
    excluded: list[dict[str, Any]] = []
    seen_links: set[tuple[str, str]] = set()
    for _, row in supplier_links.iterrows():
        current_supplier = str(row["supplier_id"])
        current_product = str(row["product_id"])
        if supplier_id and current_supplier != supplier_id:
            continue
        if (current_supplier, current_product) in seen_links:
            continue
        seen_links.add((current_supplier, current_product))
        if current_product not in products_in_scope:
            excluded.append({
                "supplier_id": current_supplier,
                "product_id": current_product,
                "reason": "product_out_of_scope",
            })
            continue
        lead_raw = _scalar(row, "lead_time_days")
        if lead_raw is None:
            excluded.append({
                "supplier_id": current_supplier,
                "product_id": current_product,
                "reason": "lead_time_missing",
            })
            continue
        lead_time_days = int(round(lead_raw))
        arrival = _order_arrival(lead_time_days, current_supplier, event, horizon_days)
        if arrival is None:
            reason = (
                "lead_time_nonpositive" if lead_time_days <= 0 else
                "lead_time_outside_horizon" if lead_time_days > horizon_days else
                "arrival_eliminated_by_scenario"
            )
            excluded.append({
                "supplier_id": current_supplier,
                "product_id": current_product,
                "reason": reason,
            })
            continue
        moq_raw = _scalar(row, "min_order_qty")
        if moq_raw is None:
            warnings.append(
                f"UNCHECKED: min_order_qty missing for supplier {current_supplier} "
                f"product {current_product}; treated as no minimum."
            )
            moq = 0.0
        else:
            moq = float(moq_raw)
        offers.append(SupplierOffer(
            supplier_id=current_supplier,
            product_id=current_product,
            unit_cost=_scalar(row, "unit_cost"),
            lead_time_days=lead_time_days,
            min_order_qty=moq,
            capacity_units=_scalar(row, "capacity_units"),
            arrival_day=arrival[0],
            arrival_factor=arrival[1],
            warehouses=tuple(sorted(set(warehouses_by_product.get(current_product, [])))),
        ))

    forecast_references = _forecast_references(
        tuple(entity_requirements), forecast_by_series
    )
    for offer in offers:
        if offer.capacity_units is None:
            warnings.append(
                f"UNCHECKED: capacity_units missing for supplier {offer.supplier_id} "
                f"product {offer.product_id}; capacity constraint not enforced."
            )
        if offer.unit_cost is None:
            warnings.append(
                f"UNCHECKED: unit_cost missing for supplier {offer.supplier_id} "
                f"product {offer.product_id}; excluded from cost objectives."
            )

    results = list(replay_run.get("results", []))
    no_action_outcome, no_action_deltas = _no_action_outcome(results)
    scenario_impact: dict[str, Any] | None = None
    if no_action_outcome is not None:
        scenario_impact = {
            "basis": "phase9_no_action_arm_minus_phase9_baseline",
            "accounting": "phase9_monte_carlo",
            "deltas": no_action_deltas or {},
            "note": (
                "Factual Phase 9 deltas of the no-action arm versus the "
                "undisrupted baseline; the optimized plan is not re-simulated."
            ),
        }

    baseline = replay_run["baseline"]
    baseline_outcome = (
        baseline.to_dict() if hasattr(baseline, "to_dict") else dict(baseline)
    )
    uncertainty = dict(replay_run.get("uncertainty", {}))
    uncertainty["requirement_intervals"] = {
        "bounds_source": "phase4_intervals_adjusted_by_scenario_point_parameters",
        "lower_upper_disclosed": True,
        "note": (
            "Demand lower/upper bounds are Phase 4 interval bounds scaled by the "
            "scenario's declared point parameters; the optimizer itself uses the "
            "point demand series (intervals are disclosed, not optimized)."
        ),
    }

    provenance = Provenance(
        source_phase="phase_9_decision_replay",
        source_module="backend.app.analytics.replay",
        replay_id=str(replay_run["replay_id"]),
        scenario_id=str(replay_run["scenario_id"]),
        scenario_fingerprint=str(replay_run["scenario_fingerprint"]),
        baseline_ref=str(replay_run["baseline_ref"]),
        sample_fingerprint=str(replay_run["sample_fingerprint"]),
        analysis_date=analysis_date,
        forecast_references=forecast_references,
        product_ids=tuple(sorted({item.product_id for item in entity_requirements})),
        warehouse_ids=tuple(sorted({item.warehouse_id for item in entity_requirements})),
        supplier_ids=tuple(sorted({offer.supplier_id for offer in offers})),
        synthetic=True,
        data_source_label="simulated",
    )

    return OptimizationInputs(
        analysis_date=analysis_date,
        horizon_days=horizon_days,
        scenario=scenario,
        event=event,
        entities=tuple(entity_requirements),
        offers=tuple(offers),
        excluded_offers=tuple(excluded),
        provenance=provenance,
        uncertainty=uncertainty,
        baseline_outcome=baseline_outcome,
        no_action_outcome=no_action_outcome,
        scenario_impact=scenario_impact,
        assumptions=ASSUMPTIONS,
        warnings=tuple(warnings),
        config=config,
        forecast_references=forecast_references,
    )

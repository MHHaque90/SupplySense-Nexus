"""Decision Replay Lab orchestration (Phase 9).

Replays explicitly defined decisions under ONE frozen disruption
scenario with ONE shared baseline and COMMON RANDOM NUMBERS:

    one frozen scenario
        → one shared baseline
        → copy-on-write decision transforms per arm
        → the same disruption mechanics and configuration
        → the SAME sampled parameter arrays for every arm
        → comparable simulated outcomes
        → baseline deltas + pairwise decision deltas

Design rules enforced here:

- Baseline built once per entity; never rebuilt per decision.
- Scenario distributions sampled once with one seeded generator; the
  identical sampled arrays feed every decision arm.
- Decisions may modify only their own declared effects; scenario
  mechanics (event, probability, duration, reductions, horizon, seed,
  simulation count) are frozen and recorded as a fingerprint.
- Validation and constraint checks run BEFORE any simulation work.
- No database access, no ranking, no recommendation, no optimization.

This analysis uses synthetic/simulated data.
"""

import copy
import hashlib
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.replay import comparison as replay_comparison
from backend.app.analytics.replay import constraints as constraint_mod
from backend.app.analytics.replay import costs as costs_mod
from backend.app.analytics.replay import effects
from backend.app.analytics.replay import outcomes as replay_outcomes
from backend.app.analytics.replay import traceability as trace_mod
from backend.app.analytics.replay import validation as validation_mod
from backend.app.analytics.replay.types import (
    DEFAULT_REPLAY_CONFIG,
    Decision,
    ReplayConfig,
    ReplayResult,
)
from backend.app.analytics.simulation import baseline as baseline_mod
from backend.app.analytics.simulation import comparison as simulation_comparison
from backend.app.analytics.simulation import monte_carlo as mc
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.analytics.simulation import simulation as sim_mod
from backend.app.analytics.simulation.types import (
    DEFAULT_SIMULATION_CONFIG,
    ScenarioOutcome,
    SimulationConfig,
    SimulationScenario,
)


def resolve_replay_id(scenario: SimulationScenario, replay_id: str | None = None) -> str:
    """Deterministic replay identity: derived from the scenario when absent."""
    return replay_id or f"replay-{scenario.scenario_id}"


def scenario_fingerprint(scenario: SimulationScenario) -> dict[str, Any]:
    """Freeze the scenario mechanics that decisions must never alter."""
    event = scenario.event
    return {
        "scenario_id": scenario.scenario_id,
        "event_id": event.event_id if event else None,
        "event_type": event.event_type if event else None,
        "event_probability": scenario.probability,
        "probability_source": scenario.probability_source,
        "probability_mode": scenario.probability_mode,
        "duration_days": event.duration_days if event else None,
        "supply_reduction": event.supply_reduction if event else None,
        "event_demand_multiplier": event.demand_multiplier if event else None,
        "analysis_date": scenario.analysis_date,
        "horizon_days": scenario.horizon_days,
        "simulation_count": scenario.simulation_count,
        "random_seed": scenario.random_seed,
    }


def prepare_shared_samples(scenario: SimulationScenario) -> dict[str, np.ndarray]:
    """Sample scenario distributions ONCE for every decision arm.

    Same scenario + same seed + same count → identical sampled arrays,
    so decision arms differ only by their declared decision effects.
    """
    rng = mc.make_generator(scenario.random_seed)
    assumptions = list(scenario.event.distributions) if scenario.event else []
    return mc.sample_parameters(assumptions, rng, scenario.simulation_count)


def sample_fingerprint(
    samples: dict[str, np.ndarray],
    scenario: SimulationScenario | None = None,
) -> str:
    """Deterministic digest identifying one shared sampled parameter set.

    Includes the scenario seed and simulation count so the fingerprint
    stays meaningful even when no distributions are configured.
    """
    digest = hashlib.sha256()
    if scenario is not None:
        digest.update(
            f"seed={scenario.random_seed};count={scenario.simulation_count}".encode()
        )
    for name in sorted(samples):
        digest.update(name.encode("utf-8"))
        values = np.ascontiguousarray(np.asarray(samples[name], dtype=float))
        digest.update(values.tobytes())
    return digest.hexdigest()[:16]


def _latest_on_hand(
    snapshots: pd.DataFrame,
    product_id: str,
    warehouse_id: str,
    analysis_date: date,
) -> float | None:
    """Latest observed on-hand at or before the analysis date."""
    if snapshots.empty:
        return None
    frame = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date)
    ].sort_values("snapshot_date")
    if frame.empty:
        return None
    return float(frame.iloc[-1]["on_hand"])


def _extend_forecast(
    forecast: ForecastInput, horizon_days: int,
) -> tuple[list[float], list[float], list[float], str | None]:
    """Cover the horizon by repeating the last forecast value when short."""
    point = [float(value) for value in forecast.point]
    lower = [float(value) for value in forecast.lower]
    upper = [float(value) for value in forecast.upper]
    note: str | None = None
    if len(point) < horizon_days:
        shortfall = horizon_days - len(point)
        last_point = point[-1] if point else 0.0
        last_lower = lower[-1] if lower else 0.0
        last_upper = upper[-1] if upper else 0.0
        point = point + [last_point] * shortfall
        lower = lower + [last_lower] * shortfall
        upper = upper + [last_upper] * shortfall
        note = (
            "Forecast shorter than the scenario horizon; extended by "
            "repeating the last value (scenario assumption)."
        )
    return point[:horizon_days], lower[:horizon_days], upper[:horizon_days], note


def _resolve_keys(scenario: SimulationScenario, snapshots, supplier_links) -> list[tuple[str, str]]:
    """Resolve scenario targets to product/warehouse series (Phase 8 rule)."""
    keys = runner_mod.resolve_series(scenario.affected_entities, snapshots, supplier_links)
    if not keys and scenario.affected_entities:
        for target in scenario.affected_entities:
            if target.get("entity_type") == "product" and target.get("warehouse_id"):
                keys.append((str(target["product_id"]), str(target["warehouse_id"])))
        keys = sorted(set(keys))
    return keys


def build_shared_baseline(
    scenario: SimulationScenario,
    forecast_by_series: dict[str, ForecastInput],
    snapshots: pd.DataFrame,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    supplier_links: pd.DataFrame,
    analysis_date: date,
) -> list[dict[str, Any]]:
    """Build the shared per-entity baseline ONCE (before any decision arm)."""
    horizon = scenario.horizon_days
    horizon_end = analysis_date + timedelta(days=horizon)
    series_keys = _resolve_keys(scenario, snapshots, supplier_links)
    if not series_keys:
        raise ValueError("No product/warehouse series resolved for the scenario targets.")
    entities: list[dict[str, Any]] = []
    for product_id, warehouse_id in series_keys:
        key = f"{product_id}|{warehouse_id}"
        forecast = forecast_by_series.get(key)
        if forecast is None or forecast.missing:
            continue
        on_hand = _latest_on_hand(snapshots, product_id, warehouse_id, analysis_date)
        if on_hand is None:
            continue
        point, lower, upper, extension_note = _extend_forecast(forecast, horizon)
        state = baseline_mod.build_baseline_series(
            product_id, warehouse_id, on_hand, point, lower, upper,
            analysis_date, horizon, shipments, po_lines, analysis_date,
            {"model_name": forecast.model_name, "origin": forecast.origin,
             "horizon": forecast.horizon},
        )
        schedule = sim_mod.build_inbound_schedule(
            product_id, shipments, po_lines, analysis_date, horizon_end,
            state["forecast_dates"],
        )
        base_run = sim_mod.run_baseline_once(on_hand, point, schedule, horizon)
        entities.append({
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "on_hand": float(on_hand),
            "demand_point": point,
            "demand_lower": lower,
            "demand_upper": upper,
            "forecast_meta": state["forecast_meta"],
            "extension_note": extension_note,
            "schedule": schedule,
            "baseline_run": replay_outcomes.summarize_run(base_run, horizon),
        })
    if not entities:
        raise ValueError(
            "No replay series resolved (missing forecasts or inventory snapshots)."
        )
    return entities


def _id_sets(
    supplier_links: pd.DataFrame, snapshots: pd.DataFrame,
) -> tuple[set[str], set[str], set[str], set[tuple[str, str]]]:
    """Known supplier/product/warehouse ids and supplier-product links."""
    supplier_ids: set[str] = set()
    product_ids: set[str] = set()
    supplier_products: set[tuple[str, str]] = set()
    if not supplier_links.empty:
        for supplier_id, product_id in zip(
            supplier_links["supplier_id"].tolist(),
            supplier_links["product_id"].tolist(),
        ):
            supplier_ids.add(str(supplier_id))
            product_ids.add(str(product_id))
            supplier_products.add((str(supplier_id), str(product_id)))
    warehouse_ids: set[str] = set()
    if not snapshots.empty:
        product_ids.update(str(value) for value in snapshots["product_id"].tolist())
        warehouse_ids.update(str(value) for value in snapshots["warehouse_id"].tolist())
    return supplier_ids, product_ids, warehouse_ids, supplier_products


def _arm_summary(
    entities: list[dict[str, Any]],
    runs_by_key: dict[tuple[str, str], list[dict[str, object]]],
    affected_by_key: dict[tuple[str, str], list[tuple[float, float, int]]],
    calendar: list[str],
    horizon_days: int,
    config: SimulationConfig,
) -> ScenarioOutcome:
    """Aggregate one decision arm with Phase 8 aggregation mathematics."""
    products, warehouses, suppliers, pairs = set(), set(), set(), 0
    inbound_count = 0
    flat: list[dict[str, object]] = []
    delayed_values: list[float] = []
    unavailable_values: list[float] = []
    for entity in entities:
        key = (str(entity["product_id"]), str(entity["warehouse_id"]))
        products.add(key[0])
        warehouses.add(key[1])
        runs = runs_by_key.get(key, [])
        flat.extend(replay_outcomes.attach_dates(runs, calendar))
        for entry in entity.get("arm_schedule", entity["schedule"]):
            inbound_count += 1
            suppliers.add(str(entry["supplier_id"]))
        for delayed, unavailable, _ in affected_by_key.get(key, []):
            delayed_values.append(delayed)
            unavailable_values.append(unavailable)
        arm_schedule = entity.get("arm_schedule", entity["schedule"])
        event_targets = set(entity.get("event_targets", []))
        if event_targets and any(
            str(entry["supplier_id"]) in event_targets for entry in arm_schedule
        ):
            pairs += 1
    outcome = replay_outcomes.aggregate(
        flat, "decision", horizon_days, sorted(products), sorted(warehouses),
        sorted(suppliers), pairs, inbound_count,
        float(np.mean(delayed_values)) if delayed_values else 0.0,
        float(np.mean(unavailable_values)) if unavailable_values else 0.0,
        config,
    )
    return outcome


def _baseline_outcome(
    entities: list[dict[str, Any]],
    calendar: list[str],
    horizon_days: int,
    config: SimulationConfig,
) -> ScenarioOutcome:
    """Aggregate the shared baseline exactly once."""
    products, warehouses, suppliers, pairs = set(), set(), set(), 0
    flat: list[dict[str, object]] = []
    for entity in entities:
        products.add(str(entity["product_id"]))
        warehouses.add(str(entity["warehouse_id"]))
        for entry in entity["schedule"]:
            suppliers.add(str(entry["supplier_id"]))
        targets = set(entity.get("event_targets", []))
        if targets and any(str(entry["supplier_id"]) in targets for entry in entity["schedule"]):
            pairs += 1
        flat.extend(replay_outcomes.attach_dates([entity["baseline_run"]], calendar))
    return replay_outcomes.aggregate_baseline(
        flat, horizon_days, sorted(products), sorted(warehouses),
        sorted(suppliers), pairs, config,
    )


def _append_unique(target: list[str], items: list[str]) -> None:
    """Append notes that are not already recorded (per-arm presentation)."""
    for item in items:
        if item not in target:
            target.append(item)


def _scenario_event_targets(scenario: SimulationScenario) -> set[str]:
    event = scenario.event
    if event is None:
        return set()
    return {str(value) for value in event.affected_suppliers}


def run_replay(
    scenario: SimulationScenario,
    decisions: list[Decision],
    forecast_by_series: dict[str, ForecastInput],
    snapshots: pd.DataFrame,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    supplier_links: pd.DataFrame,
    analysis_date: date,
    config: SimulationConfig | None = None,
    replay_config: ReplayConfig | None = None,
    replay_id: str | None = None,
) -> dict[str, Any]:
    """Replay every decision under one frozen scenario and shared baseline.

    Returns a run dictionary containing the shared baseline, one
    :class:`ReplayResult` per decision arm, pairwise factual deltas, the
    shared sampled parameter arrays, uncertainty separation, and
    scenario/baseline fingerprints. Never ranks or recommends.
    """
    config = config or DEFAULT_SIMULATION_CONFIG
    replay_config = replay_config or DEFAULT_REPLAY_CONFIG
    replay_id = resolve_replay_id(scenario, replay_id)
    horizon = scenario.horizon_days
    if not decisions:
        raise ValueError("At least one decision is required for a replay.")
    if len(decisions) > replay_config.max_decisions:
        raise ValueError(
            f"Replay received {len(decisions)} decisions; maximum is "
            f"{replay_config.max_decisions}."
        )
    if len({decision.decision_id for decision in decisions}) != len(decisions):
        raise ValueError("Decision ids must be unique within one replay.")
    fingerprint_before = scenario_fingerprint(scenario)

    # --- Validation happens before any simulation work. ---
    supplier_ids, product_ids, warehouse_ids, supplier_products = _id_sets(
        supplier_links, snapshots
    )
    warehouses = snapshots if not snapshots.empty else pd.DataFrame()
    key_series = _resolve_keys(scenario, snapshots, supplier_links)
    on_hand_lookup: dict[tuple[str, str], float] = {}
    for product_id, warehouse_id in key_series:
        value = _latest_on_hand(snapshots, product_id, warehouse_id, analysis_date)
        if value is not None:
            on_hand_lookup[(str(product_id), str(warehouse_id))] = value
    validation_notes: dict[str, list[str]] = {}
    constraint_notes: dict[str, list[str]] = {}
    skipped: list[str] = []
    scenario_series = {(str(p), str(w)) for p, w in key_series}
    for decision in decisions:
        try:
            notes = validation_mod.validate_decision(
                decision, horizon, supplier_ids, product_ids, warehouse_ids,
                supplier_products, scenario_series, on_hand_lookup,
            )
            validation_mod.validate_scenario_membership(decision, scenario_series)
            constraint_mod.check_constraints(
                decision, supplier_links, warehouses, on_hand_lookup, horizon,
            )
        except ValueError as exc:
            if replay_config.require_validation:
                raise
            skipped.append(f"{decision.decision_id}: {exc}")
            continue
        validation_notes[decision.decision_id] = notes + [
            "PASS: decision targets are inside the scenario scope."
        ]
        constraint_notes[decision.decision_id] = _constraint_notes(
            decision, supplier_links, warehouses, on_hand_lookup, horizon
        )
    active = [d for d in decisions if d.decision_id in validation_notes]
    if not active:
        raise ValueError("No valid decision remains after validation.")

    # --- One shared baseline, built once before any arm runs. ---
    entities = build_shared_baseline(
        scenario, forecast_by_series, snapshots, shipments, po_lines,
        supplier_links, analysis_date,
    )
    event_targets = _scenario_event_targets(scenario)
    for entity in entities:
        entity["event_targets"] = event_targets
    calendar = replay_outcomes.calendar_dates(scenario.analysis_date, horizon)
    baseline_outcome = _baseline_outcome(entities, calendar, horizon, config)

    # --- Common random numbers: sampled once, reused by every arm. ---
    shared_samples = prepare_shared_samples(scenario)
    fingerprint = sample_fingerprint(shared_samples, scenario)

    on_hand_base = {
        (str(entity["product_id"]), str(entity["warehouse_id"])): float(entity["on_hand"])
        for entity in entities
    }
    demand_base = {
        (str(entity["product_id"]), str(entity["warehouse_id"])): list(entity["demand_point"])
        for entity in entities
    }

    results: list[ReplayResult] = []
    arms: list[tuple[str, str, ScenarioOutcome]] = []
    arm_outcomes: dict[str, ScenarioOutcome] = {}
    for decision in active:
        # Copy-on-write: decisions never touch baseline, scenario, or loaders.
        on_hand_by_key = dict(on_hand_base)
        demand_by_key = {key: list(value) for key, value in demand_base.items()}
        effect_notes: list[str] = []
        if decision.decision_type == "INVENTORY_TRANSFER":
            transfer = effects.apply_transfer_pair(
                demand_by_key, on_hand_by_key, decision
            )
            on_hand_by_key = transfer["on_hand_by_key"]
            demand_by_key = transfer["demand_by_key"]
            effect_notes.extend(transfer["notes"])
        runs_by_key: dict[tuple[str, str], list[dict[str, object]]] = {}
        affected_by_key: dict[tuple[str, str], list[tuple[float, float, int]]] = {}
        traces: list[dict[str, Any]] = []
        for entity in entities:
            key = (str(entity["product_id"]), str(entity["warehouse_id"]))
            demand = list(entity["demand_point"])
            schedule = copy.deepcopy(entity["schedule"])
            on_hand = float(on_hand_by_key.get(key, entity["on_hand"]))
            if decision.decision_type != "INVENTORY_TRANSFER":
                applied = effects.apply_decision(
                    demand, schedule, on_hand, decision, horizon
                )
                demand = applied["demand"]
                schedule = applied["schedule"]
                on_hand = float(applied["on_hand"])
                _append_unique(effect_notes, applied["notes"])
            entity["arm_schedule"] = schedule
            runs: list[dict[str, object]] = []
            affected: list[tuple[float, float, int]] = []
            for iteration in range(scenario.simulation_count):
                params = {
                    name: float(values[iteration])
                    for name, values in shared_samples.items()
                }
                run = sim_mod.run_entity_once(
                    on_hand, demand, schedule, horizon, scenario.event, params
                )
                runs.append(replay_outcomes.summarize_run(run, horizon))
                affected.append(
                    replay_outcomes.account_effects(schedule, scenario.event, params, horizon)
                )
            runs_by_key[key] = runs
            affected_by_key[key] = affected
            arm_suppliers = sorted({str(item["supplier_id"]) for item in schedule})
            trace = trace_mod.build_decision_trace(
                scenario, decision, entity["product_id"], entity["warehouse_id"],
                arm_suppliers, entity["forecast_meta"], entity["on_hand"],
                sorted({str(item["po_id"]) for item in schedule}),
            )
            if entity["extension_note"]:
                trace["notes"] = [entity["extension_note"]]
            traces.append(trace)
        arm_outcome = _arm_summary(
            entities, runs_by_key, affected_by_key, calendar, horizon, config
        )
        deltas = simulation_comparison.compare(baseline_outcome, arm_outcome)
        cost_result = costs_mod.compute_costs(
            decision, costs_mod.modeled_quantities(decision), supplier_links,
            unmet_demand=arm_outcome.expected_unmet_demand,
        )
        results.append(ReplayResult(
            replay_id=replay_id,
            scenario_id=scenario.scenario_id,
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            outcome=arm_outcome.to_dict(),
            baseline_delta=deltas,
            decision_cost=dict(cost_result),
            validation=validation_notes.get(decision.decision_id, []),
            traceability={"entities": traces},
            constraint_notes=constraint_notes.get(decision.decision_id, []),
            effect_notes=effect_notes,
            sample_fingerprint=fingerprint,
        ))
        arms.append((decision.decision_type, decision.decision_id, arm_outcome))
        arm_outcomes[decision.decision_id] = arm_outcome

    baseline_deltas = {
        decision_id: simulation_comparison.compare(baseline_outcome, outcome)
        for _, decision_id, outcome in arms
    }
    pairwise = replay_comparison.pairwise(arms)
    if scenario_fingerprint(scenario) != fingerprint_before:
        raise ValueError("Scenario was mutated during replay; scenario mechanics are frozen.")
    return {
        "replay_id": replay_id,
        "scenario_id": scenario.scenario_id,
        "scenario": scenario.to_dict(),
        "scenario_fingerprint": fingerprint_before,
        "baseline_ref": trace_mod.baseline_ref(scenario),
        "baseline": baseline_outcome,
        "baseline_deltas": baseline_deltas,
        "decisions": list(active),
        "results": results,
        "pairwise": pairwise,
        "shared_samples": {
            name: np.asarray(values, dtype=float).tolist()
            for name, values in shared_samples.items()
        },
        "sample_fingerprint": fingerprint,
        "uncertainty": _uncertainty(scenario, active, fingerprint),
        "skipped_decisions": skipped,
        "replay_config": replay_config.to_dict(),
        "simulation_config": config.to_dict(),
        "synthetic": True,
    }


def _constraint_notes(
    decision: Decision,
    supplier_links: pd.DataFrame,
    warehouses: pd.DataFrame,
    on_hand: dict[tuple[str, str], float],
    horizon_days: int,
) -> list[str]:
    """Re-collect descriptive notes after the validating pass."""
    try:
        return constraint_mod.check_constraints(
            decision, supplier_links, warehouses, on_hand, horizon_days
        )
    except ValueError:  # pragma: no cover - already validated above
        return []


def _uncertainty(
    scenario: SimulationScenario, decisions: list[Decision], fingerprint: str,
) -> dict[str, Any]:
    """Four separate uncertainty categories; never merged into one score."""
    event = scenario.event
    return {
        "forecast_uncertainty": {
            "source": "phase4_intervals",
            "recalculated": False,
            "note": (
                "Forecast uncertainty is inherited from Phase 4 intervals and is "
                "not recalculated by replay."
            ),
        },
        "scenario_uncertainty": {
            "distributions": [item.to_dict() for item in event.distributions] if event else [],
            "note": (
                "Scenario uncertainty covers event probability, duration, supply "
                "reduction, demand multiplier, and configured distributions only."
            ),
        },
        "simulation_variability": {
            "random_seed": scenario.random_seed,
            "simulation_count": scenario.simulation_count,
            "sample_fingerprint": fingerprint,
            "note": (
                "Simulation variability comes from the seed, simulation count, and "
                "the shared Monte Carlo samples reused by every arm."
            ),
        },
        "decision_uncertainty": {
            "decisions": [
                {
                    "decision_id": decision.decision_id,
                    "decision_type": decision.decision_type,
                    "quantities": dict(decision.quantities),
                    "timing": dict(decision.timing),
                    "cost_assumptions": dict(decision.cost_assumptions),
                }
                for decision in decisions
            ],
            "note": (
                "Decision uncertainty covers decision quantities, timing, cost "
                "assumptions, and selection assumptions. It is a decision "
                "assumption layer and is never merged with forecast, scenario, or "
                "simulation uncertainty."
            ),
        },
    }


__all__ = [
    "build_shared_baseline",
    "prepare_shared_samples",
    "resolve_replay_id",
    "run_replay",
    "sample_fingerprint",
    "scenario_fingerprint",
]

"""MILP problem construction (Phase 10).

Builds a deterministic mixed-integer linear program from
:class:`~backend.app.analytics.optimization.inputs.OptimizationInputs`:

- Columns: order quantities per supplier/product/warehouse, auxiliary MOQ
  binary selectors, per-day served/unmet/balance state variables.
- Rows: daily balance dynamics identical to ``inventory_engine.run_days``
  (including masked-day semantics), demand identities, hard demand
  satisfaction where the objective requires it, MOQ linking, supplier
  capacity, per-product procurement bounds, optional budget and service-level
  rows.
- Objective: exactly one of the four declared scalar objectives.

Everything is sorted and rounded consistently so two builds from identical
inputs are byte-identical (determinism guarantee).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from backend.app.analytics.optimization.inputs import (
    OptimizationInputs,
    SupplierOffer,
)
from backend.app.analytics.optimization.types import (
    CONSTRAINT_TYPES,
    OBJECTIVES,
    Constraint,
    ConstraintRow,
    DecisionVariable,
    Objective,
    ObjectiveComponent,
    OptimizationConfig,
    OptimizationProblem,
    ProblemFormulation,
)

SOURCE_CONTRACT = "phase_9_run_replay+v1"

_INF = float("inf")


def _validate_config(config: OptimizationConfig) -> None:
    """Raise a ValueError naming the exact invalid setting."""
    if config.objective not in OBJECTIVES:
        raise ValueError(
            f"Unknown objective {config.objective!r}; expected one of "
            f"{', '.join(OBJECTIVES)}."
        )
    if config.objective == "cost_shortage_tradeoff":
        if config.shortage_penalty_per_unit is None:
            raise ValueError(
                "objective cost_shortage_tradeoff requires an explicit "
                "shortage_penalty_per_unit (> 0)."
            )
        if config.shortage_penalty_per_unit <= 0:
            raise ValueError("shortage_penalty_per_unit must be positive.")
    if config.budget is not None and config.budget <= 0:
        raise ValueError("budget must be positive when provided.")
    if config.min_fulfillment is not None and not 0.0 <= config.min_fulfillment <= 1.0:
        raise ValueError("min_fulfillment must lie in [0, 1].")
    if config.quantity_integrality not in ("integer", "continuous"):
        raise ValueError("quantity_integrality must be 'integer' or 'continuous'.")


def eligible_offers_for(
    inputs: OptimizationInputs, config: OptimizationConfig,
) -> tuple[tuple[SupplierOffer, ...], tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Filter offers for the declared objective; unknown costs are excluded.

    Cost-bearing objectives (and any configured budget) require observed
    ``unit_cost`` values; offers without one are excluded with a reason and a
    warning — never invented.
    """
    offers = sorted(
        inputs.offers, key=lambda item: (item.supplier_id, item.product_id)
    )
    needs_cost = config.objective in (
        "minimize_total_cost", "cost_shortage_tradeoff",
    ) or config.budget is not None
    if not needs_cost:
        return tuple(offers), (), ()
    kept: list[SupplierOffer] = []
    excluded: list[dict[str, Any]] = []
    for offer in offers:
        if offer.unit_cost is None:
            excluded.append({
                "supplier_id": offer.supplier_id,
                "product_id": offer.product_id,
                "reason": "unit_cost_missing_for_cost_objective",
            })
        else:
            kept.append(offer)
    warning = ()
    if excluded:
        warning = (
            f"{len(excluded)} supplier-product link(s) excluded: unit_cost "
            "missing while the declared objective or budget requires costs.",
        )
    return tuple(kept), tuple(excluded), warning


def _procurement_bounds(
    inputs: OptimizationInputs, offers: tuple[SupplierOffer, ...],
) -> dict[str, float]:
    """Per-product order ceiling: max(gross demand, largest MOQ in scope)."""
    gross: dict[str, float] = {}
    for entity in inputs.entities:
        gross[entity.product_id] = gross.get(entity.product_id, 0.0) + float(
            np.sum(entity.demand)
        )
    bounds = dict(gross)
    for offer in offers:
        current = bounds.get(offer.product_id, 0.0)
        bounds[offer.product_id] = max(current, offer.min_order_qty)
    return {key: float(value) for key, value in sorted(bounds.items())}


def _objective_spec(config: OptimizationConfig) -> Objective:
    """Build the declared objective metadata for the problem contract."""
    if config.objective == "minimize_total_cost":
        return Objective(
            name="minimize_total_cost",
            direction="minimize",
            components=(ObjectiveComponent(
                name="total_procurement_cost", weight=1.0, units="currency_units",
            ),),
            units="currency_units",
            description=(
                "Minimize total observed procurement cost of ordered units; "
                "demand satisfaction is a hard constraint for this objective."
            ),
        )
    if config.objective == "minimize_shortage":
        return Objective(
            name="minimize_shortage",
            direction="minimize",
            components=(ObjectiveComponent(
                name="total_unmet_demand", weight=1.0, units="demand_units",
            ),),
            units="demand_units",
            description=(
                "Minimize total unmet demand units over the horizon; "
                "procurement cost is not part of this objective."
            ),
        )
    if config.objective == "cost_shortage_tradeoff":
        penalty = float(config.shortage_penalty_per_unit or 0.0)
        return Objective(
            name="cost_shortage_tradeoff",
            direction="minimize",
            components=(
                ObjectiveComponent(
                    name="total_procurement_cost", weight=1.0,
                    units="currency_units",
                ),
                ObjectiveComponent(
                    name="total_unmet_demand", weight=penalty,
                    units="currency_units",
                ),
            ),
            units="currency_units",
            description=(
                "Minimize observed procurement cost plus the explicitly "
                "configured shortage penalty per unmet demand unit; the "
                "penalty value is a declared assumption, not a derived weight."
            ),
        )
    return Objective(
        name="maximize_service_fulfillment",
        direction="maximize",
        components=(ObjectiveComponent(
            name="total_served_demand", weight=1.0, units="demand_units",
        ),),
        units="demand_units",
        description=(
            "Maximize served demand units over the horizon; solver ties are "
            "resolved by solver column order (documented, not ranked)."
        ),
    )


def _digest(payload: dict[str, Any]) -> str:
    """Stable content digest for the problem id."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _round(values: Any) -> Any:
    """Round floats for digest stability without changing semantics."""
    if isinstance(values, float):
        return round(values, 6)
    if isinstance(values, (list, tuple)):
        return [_round(item) for item in values]
    if isinstance(values, dict):
        return {key: _round(value) for key, value in sorted(values.items())}
    return values


def _problem_id(inputs: OptimizationInputs, config: OptimizationConfig) -> str:
    """Deterministic problem id derived from scenario, scope, and terms."""
    payload = {
        "scenario_id": inputs.scenario["scenario_id"],
        "analysis_date": inputs.analysis_date,
        "horizon_days": inputs.horizon_days,
        "config": config.to_dict(),
        "entities": sorted(
            (
                entity.product_id,
                entity.warehouse_id,
                _round(entity.on_hand),
                _round(entity.demand),
                _round(entity.existing_inbound),
                [1 if value else 0 for value in entity.available],
            )
            for entity in inputs.entities
        ),
        "offers": sorted(
            (
                offer.supplier_id,
                offer.product_id,
                _round(offer.unit_cost),
                offer.lead_time_days,
                _round(offer.min_order_qty),
                _round(offer.capacity_units),
                offer.arrival_day,
                _round(offer.arrival_factor),
                list(offer.warehouses),
            )
            for offer in inputs.offers
        ),
    }
    return f"OPT-{_digest(payload)[:16]}"


def build_formulation(
    inputs: OptimizationInputs, config: OptimizationConfig | None = None,
) -> ProblemFormulation:
    """Build the complete MILP formulation for the declared objective.

    Raises ``ValueError`` for invalid configuration. Empty scope produces an
    empty (zero-column) formulation; the orchestration layer reports
    ``NO_DATA`` without calling a solver.
    """
    config = config or inputs.config
    _validate_config(config)
    eligible, excluded, cost_warning = eligible_offers_for(inputs, config)
    horizon = inputs.horizon_days
    entities = sorted(
        inputs.entities, key=lambda item: (item.product_id, item.warehouse_id)
    )
    procurement_bounds = _procurement_bounds(inputs, eligible)
    demand_hard = config.objective == "minimize_total_cost"
    objective = _objective_spec(config)

    names: list[str] = []
    lowers: list[float] = []
    uppers: list[float] = []
    integrality: list[int] = []
    col_index: dict[str, int] = {}
    unit_costs: dict[str, float] = {}
    integer_orders = config.quantity_integrality == "integer"

    def _add_column(
        name: str, lower: float, upper: float, is_integer: bool,
    ) -> int:
        index = len(names)
        names.append(name)
        lowers.append(lower)
        uppers.append(upper)
        integrality.append(1 if is_integer else 0)
        col_index[name] = index
        return index

    order_keys: list[tuple[str, str, str]] = []
    for offer in eligible:
        for warehouse in offer.warehouses:
            order_keys.append((offer.supplier_id, offer.product_id, warehouse))
    offer_by_key = {(item.supplier_id, item.product_id): item for item in eligible}
    for supplier_id, product_id, warehouse_id in sorted(order_keys):
        name = f"order[{supplier_id}|{product_id}|{warehouse_id}]"
        _add_column(name, 0.0, procurement_bounds.get(product_id, 0.0), integer_orders)
        if offer_by_key[(supplier_id, product_id)].unit_cost is not None:
            unit_costs[name] = float(offer_by_key[(supplier_id, product_id)].unit_cost)
    for offer in eligible:
        _add_column(f"moq_used[{offer.supplier_id}|{offer.product_id}]", 0.0, 1.0, True)

    balance_index: dict[tuple[str, str], np.ndarray] = {}
    served_index: dict[tuple[str, str], np.ndarray] = {}
    unmet_index: dict[tuple[str, str], np.ndarray] = {}
    total_demand = 0.0
    for entity in entities:
        key = (entity.product_id, entity.warehouse_id)
        balance = np.empty(horizon + 1, dtype=int)
        served = np.empty(horizon, dtype=int)
        unmet = np.empty(horizon, dtype=int)
        balance[0] = _add_column(
            f"balance[{entity.product_id}|{entity.warehouse_id}]:day00",
            entity.on_hand, entity.on_hand, False,
        )
        for day in range(1, horizon + 1):
            balance[day] = _add_column(
                f"balance[{entity.product_id}|{entity.warehouse_id}]:day{day:02d}",
                0.0, _INF, False,
            )
        for day in range(horizon):
            demand_value = float(entity.demand[day])
            total_demand += demand_value
            served[day] = _add_column(
                f"served[{entity.product_id}|{entity.warehouse_id}]:day{day:02d}",
                0.0, demand_value, False,
            )
            unmet[day] = _add_column(
                f"unmet[{entity.product_id}|{entity.warehouse_id}]:day{day:02d}",
                0.0, demand_value, False,
            )
        balance_index[key] = balance
        served_index[key] = served
        unmet_index[key] = unmet

    row_specs: list[tuple[str, str, dict[int, float], float | None, float | None]] = []

    def _add_row(
        name: str, row_type: str, coefficients: dict[int, float],
        lower: float | None, upper: float | None,
    ) -> None:
        if row_type not in CONSTRAINT_TYPES:
            raise ValueError(f"Unknown constraint type {row_type!r}.")
        row_specs.append((name, row_type, coefficients, lower, upper))

    for entity in entities:
        key = (entity.product_id, entity.warehouse_id)
        balance = balance_index[key]
        served = served_index[key]
        unmet = unmet_index[key]
        for day in range(horizon):
            demand_value = float(entity.demand[day])
            identity: dict[int, float] = {int(unmet[day]): 1.0, int(served[day]): 1.0}
            _add_row(
                f"daily_demand_identity:{entity.product_id}|{entity.warehouse_id}"
                f":day{day:02d}",
                "daily_balance", identity, demand_value, demand_value,
            )
            dynamic: dict[int, float] = {
                int(balance[day + 1]): 1.0,
                int(balance[day]): -1.0,
                int(served[day]): 1.0,
            }
            if entity.available[day]:
                dynamic_row_rhs_offset = float(entity.existing_inbound[day])
                for offer in eligible:
                    if offer.arrival_day != day:
                        continue
                    if entity.product_id != offer.product_id:
                        continue
                    if entity.warehouse_id not in offer.warehouses:
                        continue
                    name = (
                        f"order[{offer.supplier_id}|{offer.product_id}"
                        f"|{entity.warehouse_id}]"
                    )
                    dynamic[col_index[name]] = (
                        dynamic.get(col_index[name], 0.0) - offer.arrival_factor
                    )
                _add_row(
                    f"daily_balance:{entity.product_id}|{entity.warehouse_id}"
                    f":day{day:02d}",
                    "daily_balance", dynamic, dynamic_row_rhs_offset,
                    dynamic_row_rhs_offset,
                )
            else:
                _add_row(
                    f"daily_balance:{entity.product_id}|{entity.warehouse_id}"
                    f":day{day:02d}",
                    "daily_balance", {
                        int(balance[day + 1]): 1.0, int(balance[day]): -1.0,
                    }, 0.0, 0.0,
                )
                _add_row(
                    f"availability:{entity.product_id}|{entity.warehouse_id}"
                    f":day{day:02d}",
                    "daily_balance", {int(served[day]): 1.0}, 0.0, 0.0,
                )
        if demand_hard:
            _add_row(
                f"demand_satisfaction:{entity.product_id}|{entity.warehouse_id}",
                "demand_satisfaction",
                {int(column): 1.0 for column in unmet},
                0.0, 0.0,
            )

    products = sorted({entity.product_id for entity in entities})
    for product_id in products:
        order_columns = [
            col_index[f"order[{supplier_id}|{product_id}|{warehouse_id}]"]
            for supplier_id, current_product, warehouse_id in sorted(order_keys)
            if current_product == product_id
        ]
        if order_columns:
            _add_row(
                f"over_purchase_bound:{product_id}",
                "over_purchase_bound",
                {column: 1.0 for column in order_columns},
                None, procurement_bounds.get(product_id, 0.0),
            )

    for offer in eligible:
        order_columns = [
            col_index[f"order[{offer.supplier_id}|{offer.product_id}|{warehouse}]"]
            for warehouse in offer.warehouses
        ]
        binary = col_index[f"moq_used[{offer.supplier_id}|{offer.product_id}]"]
        minimum: dict[int, float] = {binary: -offer.min_order_qty}
        for column in order_columns:
            minimum[column] = minimum.get(column, 0.0) + 1.0
        _add_row(
            f"minimum_order_quantity:{offer.supplier_id}|{offer.product_id}:minimum",
            "minimum_order_quantity", minimum, 0.0, None,
        )
        linking: dict[int, float] = {binary: -procurement_bounds.get(
            offer.product_id, 0.0,
        )}
        for column in order_columns:
            linking[column] = linking.get(column, 0.0) + 1.0
        _add_row(
            f"minimum_order_quantity:{offer.supplier_id}|{offer.product_id}:linking",
            "minimum_order_quantity", linking, None, 0.0,
        )
        if offer.capacity_units is not None:
            _add_row(
                f"supplier_capacity:{offer.supplier_id}|{offer.product_id}",
                "supplier_capacity",
                {column: 1.0 for column in order_columns},
                None, offer.capacity_units,
            )

    if config.budget is not None:
        budget_row: dict[int, float] = {}
        for name, cost in sorted(unit_costs.items()):
            budget_row[col_index[name]] = cost
        if budget_row:
            _add_row("budget", "budget", budget_row, None, float(config.budget))

    if config.min_fulfillment is not None and total_demand > 0:
        service_row: dict[int, float] = {}
        for key, columns in sorted(served_index.items()):
            for column in columns:
                service_row[int(column)] = 1.0
        _add_row(
            "service_level_minimum", "service_level_minimum", service_row,
            float(config.min_fulfillment) * total_demand, None,
        )

    row_count = len(row_specs)
    column_count = len(names)
    matrix = np.zeros((row_count, column_count), dtype=float)
    rows: list[ConstraintRow] = []
    row_lower = np.empty(row_count, dtype=float)
    row_upper = np.empty(row_count, dtype=float)
    for position, (name, row_type, coefficients, lower, upper) in enumerate(row_specs):
        for column, value in coefficients.items():
            matrix[position, column] += value
        rows.append(ConstraintRow(
            name=name, type=row_type,
            lower=None if lower is None else float(lower),
            upper=None if upper is None else float(upper),
        ))
        row_lower[position] = -_INF if lower is None else float(lower)
        row_upper[position] = _INF if upper is None else float(upper)

    c_vector = np.zeros(column_count, dtype=float)
    if config.objective in ("minimize_total_cost", "cost_shortage_tradeoff"):
        for name, cost in sorted(unit_costs.items()):
            c_vector[col_index[name]] += cost
    if config.objective in ("minimize_shortage", "cost_shortage_tradeoff"):
        penalty = 1.0
        if config.objective == "cost_shortage_tradeoff":
            penalty = float(config.shortage_penalty_per_unit or 0.0)
        for name in names:
            if name.startswith("unmet["):
                c_vector[col_index[name]] += penalty
    if config.objective == "maximize_service_fulfillment":
        for name in names:
            if name.startswith("served["):
                c_vector[col_index[name]] = -1.0

    declared: list[Constraint] = [
        Constraint(
            name="daily_balance",
            type="daily_balance",
            expression=(
                "balance[t+1] = balance[t] + available_inbound[t] + "
                "eligible_order_arrivals[t] - served[t]; masked warehouse days "
                "drop inbound and force served = 0 (Phase 8 run_days semantics)"
            ),
            bound=None,
            units="demand_units",
            hard_or_soft="hard",
            source="phase_8_inventory_engine",
            description=(
                f"Daily balance dynamics for {len(entities)} entity/entities "
                f"over {horizon} days, identical to inventory_engine.run_days."
            ),
        ),
        Constraint(
            name="demand_satisfaction",
            type="demand_satisfaction",
            expression="sum(unmet over horizon) = 0 per entity",
            bound=0.0,
            units="demand_units",
            hard_or_soft="hard" if demand_hard else "soft",
            source="phase_10_objective_policy",
            description=(
                "Hard feasibility constraint for minimize_total_cost; declared "
                "as soft for the other objectives where shortage is priced or "
                "maximized by the objective itself."
            ),
        ),
        Constraint(
            name="lead_time_horizon",
            type="lead_time_horizon",
            expression="1 <= lead_time_days <= horizon and arrival not eliminated",
            bound=None,
            units="days",
            hard_or_soft="hard",
            source="phase_10_scope_rule",
            description=(
                "Supplier-product links whose effective arrival falls outside "
                "the horizon are excluded with a recorded reason."
            ),
        ),
    ]
    for offer in eligible:
        declared.append(Constraint(
            name=f"minimum_order_quantity:{offer.supplier_id}|{offer.product_id}",
            type="minimum_order_quantity",
            expression=(
                "min_order_qty * moq_used <= total_ordered <= "
                "procurement_bound * moq_used"
            ),
            bound=offer.min_order_qty,
            units="demand_units",
            hard_or_soft="hard",
            source="supplier_link_observed",
            description=(
                "Observed min_order_qty for the supplier-product link; the "
                "binary selector is an auxiliary solver variable."
            ),
        ))
        if offer.capacity_units is not None:
            declared.append(Constraint(
                name=f"supplier_capacity:{offer.supplier_id}|{offer.product_id}",
                type="supplier_capacity",
                expression="total_ordered <= capacity_units",
                bound=offer.capacity_units,
                units="demand_units",
                hard_or_soft="hard",
                source="supplier_link_observed",
                description="Observed capacity_units for the supplier-product link.",
            ))
    for product_id in products:
        declared.append(Constraint(
            name=f"over_purchase_bound:{product_id}",
            type="over_purchase_bound",
            expression="total ordered for product <= procurement bound",
            bound=procurement_bounds.get(product_id),
            units="demand_units",
            hard_or_soft="hard",
            source="phase_10_scope_rule",
            description=(
                "Ordering ceiling: max(gross in-scope demand, largest MOQ in "
                "scope); prevents unbounded inventory accumulation."
            ),
        ))
    if config.budget is not None:
        declared.append(Constraint(
            name="budget",
            type="budget",
            expression="sum(unit_cost * ordered) <= budget",
            bound=float(config.budget),
            units="currency_units",
            hard_or_soft="hard",
            source="user_configuration",
            description="Explicitly configured hard procurement budget.",
        ))
    if config.min_fulfillment is not None:
        declared.append(Constraint(
            name="service_level_minimum",
            type="service_level_minimum",
            expression="served / demand >= min_fulfillment",
            bound=float(config.min_fulfillment),
            units="fraction",
            hard_or_soft="hard",
            source="user_configuration",
            description="Explicitly configured hard minimum fulfillment rate.",
        ))

    decision_variables = tuple(
        DecisionVariable(
            name=f"order[{supplier_id}|{product_id}|{warehouse_id}]",
            entity_type="supplier_product_warehouse",
            entity_id=f"{supplier_id}|{product_id}|{warehouse_id}",
            supplier_id=supplier_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            lower_bound=0.0,
            upper_bound=procurement_bounds.get(product_id),
            integrality="integer" if integer_orders else "continuous",
            units="demand_units",
            source="phase_10_decision_variable",
            description=(
                f"Ordered units of {product_id} from {supplier_id} for "
                f"{warehouse_id}; arrival horizon day "
                f"{offer_by_key[(supplier_id, product_id)].arrival_day}."
            ),
        )
        for supplier_id, product_id, warehouse_id in sorted(order_keys)
    )

    parameters: dict[str, Any] = {
        "horizon_days": horizon,
        "objective_key": config.objective,
        "quantity_integrality": config.quantity_integrality,
        "demand_satisfaction_hard": demand_hard,
        "shortage_penalty_per_unit": config.shortage_penalty_per_unit,
        "budget": config.budget,
        "min_fulfillment": config.min_fulfillment,
        "total_demand_units": round(total_demand, 6),
        "entity_count": len(entities),
        "order_variable_count": len(order_keys),
        "auxiliary_variables": (
            "moq_used[supplier|product] binary selectors (internal; excluded "
            "from decision_values)"
        ),
        "eligible_offers": [
            {
                "supplier_id": offer.supplier_id,
                "product_id": offer.product_id,
                "unit_cost": offer.unit_cost,
                "lead_time_days": offer.lead_time_days,
                "min_order_qty": offer.min_order_qty,
                "capacity_units": offer.capacity_units,
                "arrival_day": offer.arrival_day,
                "arrival_factor": round(offer.arrival_factor, 6),
                "warehouses": list(offer.warehouses),
            }
            for offer in eligible
        ],
        "excluded_offers": [
            dict(item) for item in inputs.excluded_offers
        ] + [dict(item) for item in excluded],
        "event_point_parameters": _event_parameters(inputs),
        "procurement_bounds": {
            key: round(value, 6) for key, value in procurement_bounds.items()
        },
    }
    if cost_warning:
        parameters["cost_filter_warning"] = cost_warning[0]

    problem = OptimizationProblem(
        problem_id=_problem_id(inputs, config),
        scenario_id=str(inputs.scenario["scenario_id"]),
        analysis_date=inputs.analysis_date,
        horizon=horizon,
        objective=objective,
        decision_variables=decision_variables,
        constraints=tuple(declared),
        parameters=parameters,
        assumptions=tuple(inputs.assumptions),
        provenance=inputs.provenance,
        source_phase="phase_10_optimization",
        source_contract=SOURCE_CONTRACT,
    )
    return ProblemFormulation(
        problem=problem,
        variable_names=tuple(names),
        objective_vector=c_vector,
        variable_lower=np.asarray(lowers, dtype=float),
        variable_upper=np.asarray(uppers, dtype=float),
        integrality=np.asarray(integrality, dtype=int),
        constraint_matrix=matrix,
        rows=tuple(rows),
        unit_costs=dict(sorted(unit_costs.items())),
        total_demand=float(total_demand),
        horizon=horizon,
    )


def _event_parameters(inputs: OptimizationInputs) -> dict[str, Any] | None:
    """Declare the exact point parameters used for event effects."""
    event = inputs.event
    if not event:
        return None
    parts = event.get("components") or [event]
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "duration_days": event.get("duration_days"),
        "probability": event.get("probability"),
        "parts": [
            {
                "event_type": part.get("event_type"),
                "supply_reduction": part.get("supply_reduction"),
                "lead_time_delay_days": part.get("lead_time_delay_days"),
                "demand_multiplier": part.get("demand_multiplier"),
            }
            for part in parts
        ],
        "note": (
            "Point parameters of the declared event; Monte Carlo samples from "
            "the replay run are not resampled (deterministic optimization)."
        ),
    }

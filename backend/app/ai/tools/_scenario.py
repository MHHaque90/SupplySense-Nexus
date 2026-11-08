"""Shared scenario assembly for simulation, replay, and optimization tools.

All three tools build ONE frozen scenario contract from declared inputs:

- ``event_template`` — a named Phase 8 template (validated against
  ``events.TEMPLATES``; default ``SUPPLIER_OUTAGE``).
- ``event parameter overrides`` — duration/supply/lead-time/demand knobs.
- Optional target ids (validated against the org scope). With no explicit
  targets the scenario scope covers the whole organization; this defaulting
  is declared in the tool limitations so it is never invisible.

Outputs are always labeled ``simulated`` by the underlying reports.
"""

import uuid
from dataclasses import dataclass, field

from backend.app.ai.tools import _context as ctx
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod

_EVENT_OVERRIDE_KEYS = (
    "duration_days",
    "supply_reduction",
    "lead_time_delay_days",
    "demand_multiplier",
)


@dataclass
class ScenarioBundle:
    """Prepared org scope, frames, forecasts, and frozen scenario."""

    scope: ctx.OrgScope
    frames: ctx.Frames
    analysis_date: object
    scenario: object
    replay_id: str
    forecasts: dict
    notes: list[str] = field(default_factory=list)


def scenario_properties() -> dict[str, dict[str, object]]:
    """Shared JSON-parameter schema for scenario-driven tools."""
    return {
        "event_template": {
            "type": "string",
            "description": (
                "Named disruption template: SUPPLIER_OUTAGE, SUPPLIER_DELAY, "
                "SHIPMENT_DELAY, SUPPLY_REDUCTION, WAREHOUSE_DISRUPTION, "
                "DEMAND_SPIKE, or COMBINED_DISRUPTION. Default SUPPLIER_OUTAGE."
            ),
            "maxLength": 40,
        },
        "duration_days": {"type": "integer", "description": "Disruption duration in days (1..365)."},
        "supply_reduction": {
            "type": "number",
            "description": "Fraction of supply removed, 0..1.",
        },
        "lead_time_delay_days": {
            "type": "integer",
            "description": "Lead-time delay in days (>= 0).",
        },
        "demand_multiplier": {
            "type": "number",
            "description": "Demand multiplier (>= 0).",
        },
        "product_id": {"type": "string", "description": "Target product (must be in your organization).", "maxLength": 36},
        "warehouse_id": {"type": "string", "description": "Target warehouse (must be in your organization).", "maxLength": 36},
        "supplier_id": {"type": "string", "description": "Target supplier (must be in your organization).", "maxLength": 36},
        "analysis_date": {"type": "string", "description": "Analysis date YYYY-MM-DD (default: latest data date).", "maxLength": 10},
        "horizon_days": {"type": "integer", "description": "Simulation horizon 1..180 days (default 28)."},
        "simulation_count": {
            "type": "integer",
            "description": "Monte Carlo iterations 1..500 (default 20).",
        },
        "random_seed": {"type": "integer", "description": "Random seed (default 42)."},
    }


def validate_scenario_numbers(params: dict) -> tuple[int, int, int]:
    """Validate shared numeric parameters; returns horizon/count/seed."""
    horizon = int(params.get("horizon_days") or ctx.DEFAULT_HORIZON_DAYS)
    if not 1 <= horizon <= 180:
        raise ValueError("horizon_days must be within [1, 180].")
    count = int(params.get("simulation_count") or ctx.DEFAULT_SIMULATION_COUNT)
    if not 1 <= count <= 500:
        raise ValueError("simulation_count must be within [1, 500].")
    seed = int(params.get("random_seed") or 42)
    return horizon, count, seed


def build_event(params: dict) -> tuple[object, list[str]]:
    """Build and validate one disruption event from template + overrides."""
    notes: list[str] = []
    template = str(params.get("event_template") or "SUPPLIER_OUTAGE")
    if template not in events_mod.TEMPLATES:
        raise ValueError(
            f"Unknown event_template {template!r}. Valid: "
            f"{sorted(events_mod.TEMPLATES)}."
        )
    overrides = {
        key: params[key]
        for key in _EVENT_OVERRIDE_KEYS
        if params.get(key) is not None
    }
    event = events_mod.apply_template(
        template,
        event_id=f"{template.lower()}-{uuid.uuid4().hex[:8]}",
        start_date="",
        **overrides,
    )
    events_mod.validate_event(event, check_targets=False)
    notes.append(
        f"Event template {template} applied with declared overrides "
        f"({', '.join(sorted(overrides)) or 'no overrides'})."
    )
    return event, notes


def resolve_entities(scope: ctx.OrgScope, frames, params: dict) -> tuple[list, list[str]]:
    """Resolve scenario entities, defaulting to the full org scope."""
    notes: list[str] = []
    explicit = any(
        params.get(key) for key in ("supplier_id", "product_id", "warehouse_id")
    )
    supplier_ids = (
        [params["supplier_id"]] if params.get("supplier_id") else list(scope.supplier_ids)
    )
    product_ids = (
        [params["product_id"]] if params.get("product_id") else list(scope.product_ids)
    )
    warehouse_ids = (
        [params["warehouse_id"]]
        if params.get("warehouse_id")
        else list(scope.warehouse_ids)
    )
    entities = targets_mod.resolve_explicit(
        supplier_ids=supplier_ids,
        product_ids=product_ids,
        warehouse_ids=warehouse_ids,
    )
    linked_suppliers = (
        [params["supplier_id"]] if params.get("supplier_id") else list(scope.supplier_ids)
    )
    for supplier_id in linked_suppliers:
        entities.extend(
            targets_mod.resolve_supplier_products(supplier_id, frames.supplier_links)
        )
    if not explicit:
        notes.append(
            "No target ids were provided; the scenario scope covers every "
            "supplier, product, and warehouse in your organization."
        )
    if not entities:
        raise ValueError(
            "No scenario entities resolved for your organization "
            "(missing suppliers, products, and warehouses)."
        )
    return entities, notes


async def prepare_scenario(
    context,
    scope: ctx.OrgScope,
    frames,
    analysis_date,
    tool_name: str,
) -> ScenarioBundle:
    """Assemble the frozen scenario plus org-scoped forecast inputs."""
    params = context.params
    horizon, count, seed = validate_scenario_numbers(params)
    event, notes = build_event(params)
    entities, entity_notes = resolve_entities(scope, frames, params)
    notes.extend(entity_notes)
    scenario = scenarios_mod.build_scenario(
        scenario_id=f"{tool_name}-{uuid.uuid4().hex[:10]}",
        event=event,
        analysis_date=analysis_date.isoformat(),
        horizon_days=horizon,
        affected_entities=entities,
        simulation_count=count,
        random_seed=seed,
        name=f"{tool_name} scenario",
    )
    replay_id = replay_mod.resolve_replay_id(scenario)
    forecasts = await ctx.build_forecasts(
        context.session,
        frames,
        scope,
        analysis_date,
        params.get("product_id"),
        params.get("warehouse_id"),
    )
    if not forecasts:
        raise ValueError(
            "No forecast inputs could be built for this organization "
            "(missing demand history or forecast rows)."
        )
    return ScenarioBundle(
        scope=scope,
        frames=frames,
        analysis_date=analysis_date,
        scenario=scenario,
        replay_id=replay_id,
        forecasts=forecasts,
        notes=notes,
    )


__all__ = [
    "ScenarioBundle",
    "build_event",
    "prepare_scenario",
    "resolve_entities",
    "scenario_properties",
    "validate_scenario_numbers",
]

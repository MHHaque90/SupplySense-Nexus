"""Disruption event definitions, validation, and templates (Phase 8).

Every event carries explicit assumptions. Reports must distinguish
OBSERVED DATA from SCENARIO ASSUMPTION: assumption values are never
historical facts.
"""

from backend.app.analytics.simulation.types import EVENT_TYPES, DisruptionEvent

_ASSUMPTION_NOTE = "This value is a scenario assumption and is not an observed historical fact."


def validate_event(event: DisruptionEvent, check_targets: bool = True) -> list[str]:
    """Validate event-specific parameters, returning assumption notes.

    Raises ValueError for invalid combinations. With check_targets=False,
    affected-entity presence is deferred to scenario assembly (templates
    define parameters; targeting resolves entities).
    """
    if event.event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unsupported event type: {event.event_type}. Valid: {sorted(EVENT_TYPES)}."
        )
    if event.duration_days < 1:
        raise ValueError("duration_days must be at least 1.")
    if not 0.0 <= event.supply_reduction <= 1.0:
        raise ValueError("supply_reduction must be within [0, 1].")
    if event.lead_time_delay_days < 0:
        raise ValueError("lead_time_delay_days must be non-negative.")
    if event.demand_multiplier <= 0:
        raise ValueError("demand_multiplier must be positive.")
    notes = [f"duration_days = {event.duration_days}. {_ASSUMPTION_NOTE}"]
    if event.event_type == "SUPPLIER_DISRUPTION":
        if check_targets and not event.affected_suppliers:
            raise ValueError("SUPPLIER_DISRUPTION requires affected_suppliers.")
        if event.supply_reduction <= 0:
            raise ValueError("SUPPLIER_DISRUPTION requires supply_reduction > 0.")
        notes.append(f"supply_reduction = {event.supply_reduction}. {_ASSUMPTION_NOTE}")
    elif event.event_type == "SHIPMENT_DELAY":
        if event.lead_time_delay_days <= 0:
            raise ValueError("SHIPMENT_DELAY requires lead_time_delay_days > 0.")
        notes.append(f"lead_time_delay_days = {event.lead_time_delay_days}. {_ASSUMPTION_NOTE}")
    elif event.event_type == "LEAD_TIME_DELAY":
        if event.lead_time_delay_days <= 0:
            raise ValueError("LEAD_TIME_DELAY requires lead_time_delay_days > 0.")
        notes.append(f"lead_time_delay_days = {event.lead_time_delay_days}. {_ASSUMPTION_NOTE}")
    elif event.event_type == "SUPPLY_REDUCTION":
        if event.supply_reduction <= 0:
            raise ValueError("SUPPLY_REDUCTION requires supply_reduction > 0.")
        notes.append(f"supply_reduction = {event.supply_reduction}. {_ASSUMPTION_NOTE}")
    elif event.event_type == "WAREHOUSE_DISRUPTION":
        if check_targets and not event.affected_warehouses:
            raise ValueError("WAREHOUSE_DISRUPTION requires affected_warehouses.")
        if event.warehouse_available:
            raise ValueError("WAREHOUSE_DISRUPTION requires warehouse_available = false.")
        notes.append(f"warehouse_available = false. {_ASSUMPTION_NOTE}")
    elif event.event_type == "DEMAND_SHOCK":
        if event.demand_multiplier == 1.0:
            raise ValueError("DEMAND_SHOCK requires demand_multiplier != 1.0.")
        notes.append(f"demand_multiplier = {event.demand_multiplier}. {_ASSUMPTION_NOTE}")
    elif event.event_type == "COMBINED_DISRUPTION":
        for component in event.components:
            if component.event_type == "COMBINED_DISRUPTION":
                raise ValueError("Nested COMBINED_DISRUPTION components are not allowed.")
            validate_event(component, check_targets=check_targets)
        notes.append(
            f"Combined components: {[c.event_type for c in event.components]}. {_ASSUMPTION_NOTE}"
        )
    return notes


def describe_event(event: DisruptionEvent) -> str:
    """Describe an event in scenario language (never as prediction)."""
    return (
        f"Under the configured disruption scenario '{event.name}' "
        f"({event.event_type}), conditional on the event occurring: "
        f"duration {event.duration_days} days from {event.start_date or 'the analysis date'}."
    )


TEMPLATES: dict[str, dict[str, object]] = {
    "SUPPLIER_OUTAGE": {
        "event_type": "SUPPLIER_DISRUPTION",
        "duration_days": 14,
        "supply_reduction": 1.0,
        "description": "Targeted supplier relationships deliver nothing during the window.",
    },
    "SUPPLIER_DELAY": {
        "event_type": "LEAD_TIME_DELAY",
        "duration_days": 21,
        "lead_time_delay_days": 7,
        "description": "Targeted inbound arrives later by the configured delay.",
    },
    "SHIPMENT_DELAY": {
        "event_type": "SHIPMENT_DELAY",
        "duration_days": 14,
        "lead_time_delay_days": 5,
        "description": "Expected arrivals shift later by the configured delay.",
    },
    "SUPPLY_REDUCTION": {
        "event_type": "SUPPLY_REDUCTION",
        "duration_days": 30,
        "supply_reduction": 0.4,
        "description": "Available supply reduced by the configured fraction.",
    },
    "WAREHOUSE_DISRUPTION": {
        "event_type": "WAREHOUSE_DISRUPTION",
        "duration_days": 7,
        "warehouse_available": False,
        "description": "Targeted warehouse inventory is inaccessible during the window.",
    },
    "DEMAND_SPIKE": {
        "event_type": "DEMAND_SHOCK",
        "duration_days": 14,
        "demand_multiplier": 1.2,
        "description": "Demand scaled by the configured multiplier during the window.",
    },
    "COMBINED_DISRUPTION": {
        "event_type": "COMBINED_DISRUPTION",
        "duration_days": 14,
        "description": "Explicitly defined component events applied together.",
    },
}


def apply_template(
    template_name: str,
    event_id: str,
    start_date: str = "",
    **overrides,
) -> DisruptionEvent:
    """Build an event from a named template with explicit overrides."""
    if template_name not in TEMPLATES:
        raise ValueError(
            f"Unknown template: {template_name}. Valid: {sorted(TEMPLATES)}."
        )
    params: dict[str, object] = dict(TEMPLATES[template_name])
    params.update(overrides)
    params["event_id"] = event_id
    params["name"] = str(params.get("name", template_name))
    params["start_date"] = start_date
    params["assumptions"] = [
        f"{key} = {value}. {_ASSUMPTION_NOTE}"
        for key, value in sorted(params.items())
        if key in ("duration_days", "supply_reduction", "lead_time_delay_days",
                   "demand_multiplier", "warehouse_available")
    ]
    event = DisruptionEvent(**{k: v for k, v in params.items() if k in DisruptionEvent.__dataclass_fields__})
    # Targeting resolves at scenario assembly; templates define parameters.
    validate_event(event, check_targets=False)
    return event

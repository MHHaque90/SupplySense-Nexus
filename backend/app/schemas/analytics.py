"""Pydantic request schemas for the Phase 12A dashboard API layer.

All request models reject unknown fields (``extra="forbid"``) so that
identity or configuration can never be injected through the body — the
authenticated ``Authorization`` header is the only identity source.

Validation bounds mirror the existing engine contracts exactly:

- Phase 8: horizon 1..180 days, simulation_count 1..500, the three
  probability modes, the seven event types, the named templates.
- Phase 9: the eight locked decision types and ``max_decisions``.
- Phase 10: the four locked objectives and solver time limit 1..120 s.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Mirror of Phase 8 ``simulation.types.EVENT_TYPES`` (test-enforced).
EventType = Literal[
    "SUPPLIER_DISRUPTION",
    "SHIPMENT_DELAY",
    "LEAD_TIME_DELAY",
    "SUPPLY_REDUCTION",
    "WAREHOUSE_DISRUPTION",
    "DEMAND_SHOCK",
    "COMBINED_DISRUPTION",
]

#: Mirror of Phase 9 ``replay.types.DECISION_TYPES`` (test-enforced).
DecisionType = Literal[
    "NO_ACTION",
    "EXPEDITE_INBOUND",
    "ALTERNATIVE_SUPPLIER",
    "SUPPLIER_ALLOCATION_CHANGE",
    "INVENTORY_TRANSFER",
    "DEMAND_ADJUSTMENT",
    "PURCHASE_ORDER_ADJUSTMENT",
    "COMBINED_ACTION",
]

#: Mirror of Phase 10 ``optimization.types.OBJECTIVES`` (test-enforced).
OptimizationObjective = Literal[
    "minimize_total_cost",
    "minimize_shortage",
    "cost_shortage_tradeoff",
    "maximize_service_fulfillment",
]

#: Mirror of Phase 10 allowed solver statuses (test-enforced).
SolverStatus = Literal[
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "UNBOUNDED",
    "ERROR",
    "NO_DATA",
]

ProbabilityMode = Literal["deterministic", "explicit", "empirical"]

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class StrictRequest(BaseModel):
    """Base request body: unknown fields are rejected (422)."""

    model_config = ConfigDict(extra="forbid")


class ScenarioRequest(StrictRequest):
    """Shared scenario contract for simulation, replay, and optimization.

    Exactly one of ``event_template`` (a Phase 8 named template) or
    ``event_type`` (a Phase 8 event type) drives the disruption event;
    the router rejects requests that provide both. When neither is
    provided, the default ``SUPPLIER_OUTAGE`` template applies.
    """

    event_template: str | None = Field(
        None, max_length=40, description="Phase 8 named template (default SUPPLIER_OUTAGE)."
    )
    event_type: EventType | None = Field(
        None, description="Direct Phase 8 event type (alternative to event_template)."
    )
    duration_days: int | None = Field(None, ge=1, le=365)
    supply_reduction: float | None = Field(None, ge=0.0, le=1.0)
    lead_time_delay_days: int | None = Field(None, ge=0)
    demand_multiplier: float | None = Field(None, gt=0.0)
    probability_mode: ProbabilityMode = "deterministic"
    probability: float | None = Field(None, ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    product_id: str | None = Field(None, max_length=36)
    warehouse_id: str | None = Field(None, max_length=36)
    supplier_id: str | None = Field(None, max_length=36)
    analysis_date: str | None = Field(None, pattern=_DATE_PATTERN)
    horizon_days: int = Field(28, ge=1, le=180)
    simulation_count: int = Field(20, ge=1, le=500)
    random_seed: int = 42


class SimulationRunRequest(ScenarioRequest):
    """POST /api/v1/simulation/run request body."""


class DecisionArm(StrictRequest):
    """One declared Phase 9 decision arm (existing decision contract)."""

    decision_type: DecisionType
    description: str = ""
    affected_suppliers: list[str] = Field(default_factory=list)
    affected_products: list[str] = Field(default_factory=list)
    affected_warehouses: list[str] = Field(default_factory=list)
    quantities: dict[str, float] = Field(default_factory=dict)
    timing: dict[str, int] = Field(default_factory=dict)
    cost_assumptions: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    components: list["DecisionArm"] = Field(default_factory=list, max_length=8)


class ReplayRunRequest(ScenarioRequest):
    """POST /api/v1/replay/run request body.

    An empty ``decisions`` list runs only the NO_ACTION control arm
    (factual baseline outcome, no comparison claim).
    """

    decisions: list[DecisionArm] = Field(default_factory=list, max_length=16)


class OptimizationRunRequest(ScenarioRequest):
    """POST /api/v1/optimization/run request body (Phase 10 config)."""

    objective: OptimizationObjective = "minimize_total_cost"
    shortage_penalty: float | None = Field(None, gt=0.0)
    budget: float | None = Field(None, gt=0.0)
    min_fulfillment: float | None = Field(None, ge=0.0, le=1.0)
    quantity_integrality: Literal["integer", "continuous"] = "integer"
    time_limit_seconds: int = Field(15, ge=1, le=120)


__all__ = [
    "DecisionArm",
    "DecisionType",
    "EventType",
    "OptimizationObjective",
    "OptimizationRunRequest",
    "ProbabilityMode",
    "ReplayRunRequest",
    "ScenarioRequest",
    "SimulationRunRequest",
    "SolverStatus",
    "StrictRequest",
]

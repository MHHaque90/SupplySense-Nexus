"""Typed disruption simulation contracts (Phase 8)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SimulationConfig:
    """Explicit simulation configuration. Every setting documented.

    - default_horizon_days: default simulation horizon.
    - min_simulations_percentiles: minimum iterations before p05/p25/
      p50/p75/p95 are exposed.
    - min_simulations_tail: minimum iterations before p99/p90/p95 tail
      statistics are exposed.
    - max_horizon_days: upper bound guarding runaway horizons.
    - grace_days: tolerance treating near-zero delays as on-time in
      traceability summaries (not a performance claim).
    """

    default_horizon_days: int = 28
    min_simulations_percentiles: int = 20
    min_simulations_tail: int = 100
    max_horizon_days: int = 180
    grace_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "default_horizon_days": self.default_horizon_days,
            "min_simulations_percentiles": self.min_simulations_percentiles,
            "min_simulations_tail": self.min_simulations_tail,
            "max_horizon_days": self.max_horizon_days,
            "grace_days": self.grace_days,
        }


DEFAULT_SIMULATION_CONFIG = SimulationConfig()

EVENT_TYPES = (
    "SUPPLIER_DISRUPTION",
    "SHIPMENT_DELAY",
    "LEAD_TIME_DELAY",
    "SUPPLY_REDUCTION",
    "WAREHOUSE_DISRUPTION",
    "DEMAND_SHOCK",
    "COMBINED_DISRUPTION",
)

PROBABILITY_MODES = ("deterministic", "explicit", "empirical", "distribution")

PROBABILITY_SOURCES = (
    "DETERMINISTIC",
    "USER_ASSUMED",
    "EMPIRICAL",
    "DISTRIBUTION_ASSUMPTION",
)


@dataclass(frozen=True)
class DistributionAssumption:
    """An explicitly defined uncertain scenario parameter."""

    parameter: str  # e.g. "duration_days", "supply_reduction"
    distribution: str  # "triangular" or "uniform"
    minimum: float = 0.0
    mode: float = 0.0  # triangular only
    maximum: float = 0.0
    units: str = ""
    source: str = "USER_ASSUMED"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the distribution."""
        return {
            "parameter": self.parameter,
            "distribution": self.distribution,
            "minimum": self.minimum,
            "mode": self.mode,
            "maximum": self.maximum,
            "units": self.units,
            "source": self.source,
            "assumption_status": "SCENARIO_ASSUMPTION",
        }


@dataclass
class DisruptionEvent:
    """A clearly defined disruption event (assumptions, not facts)."""

    event_id: str
    event_type: str
    name: str = ""
    description: str = ""
    start_date: str = ""
    duration_days: int = 0
    affected_suppliers: list[str] = field(default_factory=list)
    affected_products: list[str] = field(default_factory=list)
    affected_warehouses: list[str] = field(default_factory=list)
    supply_reduction: float = 0.0  # 0..1 fraction of supply removed
    lead_time_delay_days: int = 0
    demand_multiplier: float = 1.0
    warehouse_available: bool = True
    probability_mode: str = "deterministic"
    probability: float = 1.0
    probability_source: str = "DETERMINISTIC"
    severity: str = "medium"
    assumptions: list[str] = field(default_factory=list)
    source: str = "user_defined"
    data_source_label: str = "simulated"
    distributions: list[DistributionAssumption] = field(default_factory=list)
    components: list["DisruptionEvent"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the event."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "name": self.name,
            "description": self.description,
            "start_date": self.start_date,
            "duration_days": self.duration_days,
            "affected_suppliers": self.affected_suppliers,
            "affected_products": self.affected_products,
            "affected_warehouses": self.affected_warehouses,
            "supply_reduction": self.supply_reduction,
            "lead_time_delay_days": self.lead_time_delay_days,
            "demand_multiplier": self.demand_multiplier,
            "warehouse_available": self.warehouse_available,
            "probability_mode": self.probability_mode,
            "probability": self.probability,
            "probability_source": self.probability_source,
            "severity": self.severity,
            "assumptions": self.assumptions,
            "source": self.source,
            "data_source_label": self.data_source_label,
            "distributions": [item.to_dict() for item in self.distributions],
            "components": [item.to_dict() for item in self.components],
        }


@dataclass
class SimulationScenario:
    """A scenario binding an event to targets, horizon, and probability."""

    scenario_id: str
    name: str = ""
    description: str = ""
    analysis_date: str = ""
    horizon_days: int = 28
    event: DisruptionEvent | None = None
    affected_entities: list[dict[str, Any]] = field(default_factory=list)
    baseline_source: str = "phase5_intelligence"
    probability_mode: str = "deterministic"
    probability: float = 1.0
    probability_source: str = "DETERMINISTIC"
    simulation_count: int = 1
    random_seed: int = 42
    assumptions: list[str] = field(default_factory=list)
    source: str = "user_defined"
    data_source_label: str = "simulated"
    selection_basis: str = "explicit_user_selection"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the scenario."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "analysis_date": self.analysis_date,
            "horizon_days": self.horizon_days,
            "event": self.event.to_dict() if self.event else None,
            "affected_entities": self.affected_entities,
            "baseline_source": self.baseline_source,
            "probability_mode": self.probability_mode,
            "probability": self.probability,
            "probability_source": self.probability_source,
            "simulation_count": self.simulation_count,
            "random_seed": self.random_seed,
            "assumptions": self.assumptions,
            "source": self.source,
            "data_source_label": self.data_source_label,
            "selection_basis": self.selection_basis,
        }


@dataclass
class ScenarioOutcome:
    """Aggregated outcomes for baseline or scenario runs."""

    label: str  # "baseline" or "scenario"
    stockout_probability: float | None = None
    stockout_count: int = 0
    expected_stockout_days: float | None = None
    expected_min_inventory: float | None = None
    expected_ending_inventory: float | None = None
    inventory_depletion_probability: float | None = None
    affected_product_count: int = 0
    affected_warehouse_count: int = 0
    service_exposure_probability: float | None = None
    expected_unmet_demand: float | None = None
    median_unmet_demand: float | None = None
    p90_unmet_demand: float | None = None
    p95_unmet_demand: float | None = None
    affected_supplier_count: int = 0
    affected_supplier_product_count: int = 0
    affected_inbound_count: int = 0
    delayed_inbound_quantity: float = 0.0
    unavailable_inbound_quantity: float = 0.0
    stockout_by_day: dict[str, float | None] = field(default_factory=dict)
    first_stockout_dates: list[str | None] = field(default_factory=list)
    distributions: dict[str, dict[str, float | None]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the outcome."""
        return {
            "label": self.label,
            "stockout_probability": self.stockout_probability,
            "stockout_count": self.stockout_count,
            "expected_stockout_days": self.expected_stockout_days,
            "expected_min_inventory": self.expected_min_inventory,
            "expected_ending_inventory": self.expected_ending_inventory,
            "inventory_depletion_probability": self.inventory_depletion_probability,
            "affected_product_count": self.affected_product_count,
            "affected_warehouse_count": self.affected_warehouse_count,
            "service_exposure_probability": self.service_exposure_probability,
            "expected_unmet_demand": self.expected_unmet_demand,
            "median_unmet_demand": self.median_unmet_demand,
            "p90_unmet_demand": self.p90_unmet_demand,
            "p95_unmet_demand": self.p95_unmet_demand,
            "affected_supplier_count": self.affected_supplier_count,
            "affected_supplier_product_count": self.affected_supplier_product_count,
            "affected_inbound_count": self.affected_inbound_count,
            "delayed_inbound_quantity": self.delayed_inbound_quantity,
            "unavailable_inbound_quantity": self.unavailable_inbound_quantity,
            "stockout_by_day": self.stockout_by_day,
            "first_stockout_dates": self.first_stockout_dates,
            "distributions": self.distributions,
        }

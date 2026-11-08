"""Typed inventory intelligence contracts (Phase 5)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InventoryIntelligenceConfig:
    """Explicit thresholds for inventory signals. Every threshold documented.

    - coverage_period_days: demand window behind the reorder threshold.
    - uncertainty_buffer_factor: fraction of mean interval width added to
      the reorder threshold as an INFORMATIONAL buffer derived directly
      from forecast uncertainty (not an optimized safety stock).
    - critical_dos / at_risk_dos: days-of-supply cutoffs for health.
    - excess_dos / excess_coverage_ratio: excess-signal cutoffs.
    - urgent_days / plan_days: projected-stockout urgency cutoffs.
    - recent_window_days: window behind recent position statistics.
    - anomaly_drop_ratio / anomaly_adjustment_qty / stagnant_days:
      rule-based anomaly cutoffs.
    - min_observations: minimum history required for volatility signals.
    """

    coverage_period_days: int = 14
    uncertainty_buffer_factor: float = 0.5
    critical_dos: float = 3.0
    at_risk_dos: float = 7.0
    excess_dos: float = 60.0
    excess_coverage_ratio: float = 2.0
    urgent_days: int = 3
    plan_days: int = 14
    recent_window_days: int = 30
    anomaly_drop_ratio: float = 0.5
    anomaly_adjustment_qty: float = 100.0
    stagnant_days: int = 45
    min_observations: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "coverage_period_days": self.coverage_period_days,
            "uncertainty_buffer_factor": self.uncertainty_buffer_factor,
            "critical_dos": self.critical_dos,
            "at_risk_dos": self.at_risk_dos,
            "excess_dos": self.excess_dos,
            "excess_coverage_ratio": self.excess_coverage_ratio,
            "urgent_days": self.urgent_days,
            "plan_days": self.plan_days,
            "recent_window_days": self.recent_window_days,
            "anomaly_drop_ratio": self.anomaly_drop_ratio,
            "anomaly_adjustment_qty": self.anomaly_adjustment_qty,
            "stagnant_days": self.stagnant_days,
            "min_observations": self.min_observations,
        }


DEFAULT_INVENTORY_CONFIG = InventoryIntelligenceConfig()


@dataclass
class InventoryPosition:
    """Point-in-time inventory position for one product/warehouse."""

    product_id: str
    warehouse_id: str
    analysis_date: str
    current_on_hand: float | None
    latest_snapshot_date: str | None
    recent_average: float | None = None
    recent_minimum: float | None = None
    recent_maximum: float | None = None
    recent_volatility: float | None = None
    recent_inflow: float | None = None
    recent_outflow: float | None = None
    adjustment_count: int = 0
    stockout_observations: int = 0
    unknown: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the position."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "analysis_date": self.analysis_date,
            "current_on_hand": self.current_on_hand,
            "latest_snapshot_date": self.latest_snapshot_date,
            "recent_average": self.recent_average,
            "recent_minimum": self.recent_minimum,
            "recent_maximum": self.recent_maximum,
            "recent_volatility": self.recent_volatility,
            "recent_inflow": self.recent_inflow,
            "recent_outflow": self.recent_outflow,
            "adjustment_count": self.adjustment_count,
            "stockout_observations": self.stockout_observations,
            "unknown": self.unknown,
        }


@dataclass
class ForecastInput:
    """Phase 4 forecast consumed by inventory intelligence."""

    product_id: str
    warehouse_id: str
    origin: str
    forecast_dates: list[str] = field(default_factory=list)
    horizon: int = 0
    point: list[float] = field(default_factory=list)
    lower: list[float] = field(default_factory=list)
    upper: list[float] = field(default_factory=list)
    confidence_level: float = 0.95
    interval_method: str = ""
    model_name: str = ""
    model_version: str = ""
    demand_profile: str = ""
    validation_metric: str = ""
    validation_score: float | None = None
    validation_folds: int = 0
    explanation: str = ""
    confidence: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: str = "persisted"  # or "generated_for_analysis"
    missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the forecast input."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "origin": self.origin,
            "forecast_dates": self.forecast_dates,
            "horizon": self.horizon,
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "confidence_level": self.confidence_level,
            "interval_method": self.interval_method,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "demand_profile": self.demand_profile,
            "validation_metric": self.validation_metric,
            "validation_score": self.validation_score,
            "validation_folds": self.validation_folds,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "source": self.source,
            "missing": self.missing,
        }


@dataclass
class CoverageResult:
    """Demand coverage from forecast and historical perspectives."""

    product_id: str
    warehouse_id: str
    forecast_days_of_supply: float | None = None  # None when undefined
    forecast_days_of_supply_state: str = "unknown"  # finite|unbounded|unknown
    historical_days_of_supply: float | None = None
    coverage_ratio_point: float | None = None
    coverage_ratio_lower_demand: float | None = None
    coverage_ratio_upper_demand: float | None = None
    horizon_demand_point: float | None = None
    horizon_demand_lower: float | None = None
    horizon_demand_upper: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the coverage."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "forecast_days_of_supply": self.forecast_days_of_supply,
            "forecast_days_of_supply_state": self.forecast_days_of_supply_state,
            "historical_days_of_supply": self.historical_days_of_supply,
            "coverage_ratio_point": self.coverage_ratio_point,
            "coverage_ratio_lower_demand": self.coverage_ratio_lower_demand,
            "coverage_ratio_upper_demand": self.coverage_ratio_upper_demand,
            "horizon_demand_point": self.horizon_demand_point,
            "horizon_demand_lower": self.horizon_demand_lower,
            "horizon_demand_upper": self.horizon_demand_upper,
        }


@dataclass
class ProjectedInventoryPoint:
    """One day of the projected inventory trajectory."""

    date: str
    beginning_inventory: float
    forecast_demand: float
    lower_demand: float
    upper_demand: float
    known_inbound: float
    projected_ending: float
    projected_stockout: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the trajectory point."""
        return {
            "date": self.date,
            "beginning_inventory": self.beginning_inventory,
            "forecast_demand": self.forecast_demand,
            "lower_demand": self.lower_demand,
            "upper_demand": self.upper_demand,
            "known_inbound": self.known_inbound,
            "projected_ending": self.projected_ending,
            "projected_stockout": self.projected_stockout,
        }


@dataclass
class StockoutExposure:
    """Stockout exposure categories and evidence."""

    product_id: str
    warehouse_id: str
    current_stockout: bool = False
    projected_stockout: bool = False
    days_until_stockout: int | None = None
    projected_stockout_date: str | None = None
    horizon_stockout: bool = False
    exposure: str = "unknown"  # no_exposure|watch|elevated|immediate|unknown
    demand_remaining_at_stockout: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the exposure."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "current_stockout": self.current_stockout,
            "projected_stockout": self.projected_stockout,
            "days_until_stockout": self.days_until_stockout,
            "projected_stockout_date": self.projected_stockout_date,
            "horizon_stockout": self.horizon_stockout,
            "exposure": self.exposure,
            "demand_remaining_at_stockout": self.demand_remaining_at_stockout,
        }


@dataclass
class ReorderSignal:
    """Reorder SIGNAL (threshold crossing), never an order quantity."""

    product_id: str
    warehouse_id: str
    threshold: float | None = None
    current_inventory: float | None = None
    below_threshold: bool = False
    urgency: str = "unknown"  # no_signal|monitor|plan|urgent|unknown
    reason: str = ""
    uncertainty_buffer: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the signal."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "threshold": self.threshold,
            "current_inventory": self.current_inventory,
            "below_threshold": self.below_threshold,
            "urgency": self.urgency,
            "reason": self.reason,
            "uncertainty_buffer": self.uncertainty_buffer,
        }


@dataclass
class InventoryHealth:
    """Health classification with reason (never a prescription)."""

    product_id: str
    warehouse_id: str
    health: str = "UNKNOWN"  # STOCKOUT|CRITICAL|AT_RISK|HEALTHY|EXCESS|UNKNOWN
    reason: str = ""
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the health."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "health": self.health,
            "reason": self.reason,
            "missing_evidence": self.missing_evidence,
        }


@dataclass
class InventoryAnomaly:
    """Rule-based anomaly observation."""

    product_id: str
    warehouse_id: str
    date: str
    observed: float
    reference: float | None
    rule: str
    severity: str  # info|watch|high
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the anomaly."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "date": self.date,
            "observed": self.observed,
            "reference": self.reference,
            "rule": self.rule,
            "severity": self.severity,
            "explanation": self.explanation,
        }


@dataclass
class InventoryIntelligenceResult:
    """Full per-series inventory intelligence with forecast provenance."""

    product_id: str
    warehouse_id: str
    analysis_date: str
    position: InventoryPosition | None = None
    forecast: ForecastInput | None = None
    coverage: CoverageResult | None = None
    trajectory: list[ProjectedInventoryPoint] = field(default_factory=list)
    stockout: StockoutExposure | None = None
    health: InventoryHealth | None = None
    reorder: ReorderSignal | None = None
    uncertainty_note: str = ""
    service_note: str = ""
    synthetic: bool = True
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the result."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "analysis_date": self.analysis_date,
            "position": self.position.to_dict() if self.position else None,
            "forecast": self.forecast.to_dict() if self.forecast else None,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "trajectory": [point.to_dict() for point in self.trajectory],
            "stockout": self.stockout.to_dict() if self.stockout else None,
            "health": self.health.to_dict() if self.health else None,
            "reorder": self.reorder.to_dict() if self.reorder else None,
            "uncertainty_note": self.uncertainty_note,
            "service_note": self.service_note,
            "synthetic": self.synthetic,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
        }

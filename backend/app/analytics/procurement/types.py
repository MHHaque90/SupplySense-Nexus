"""Typed supplier & procurement intelligence contracts (Phase 6)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProcurementIntelligenceConfig:
    """Explicit thresholds for procurement signals. Every threshold documented.

    - late_grace_days: shipments arriving within this many days after the
      expected date still count as on-time (operational tolerance).
    - min_shipments: minimum delivered shipments for a reliability class;
      fewer observations yield UNKNOWN.
    - delayed_rate / high_delay_rate: late-rate cutoffs for DELAYED and
      HIGH_DELAY reliability classes.
    - variable_delay_std: delay standard-deviation cutoff for VARIABLE.
    - min_lead_time_obs: minimum observations for lead-time percentiles.
    - concentrated_share: top-supplier share flagging high concentration
      (descriptive exposure metric, not a diversification recommendation).
    - recent_window_days: window behind recent service/delay evidence.
    """

    late_grace_days: int = 0
    min_shipments: int = 5
    delayed_rate: float = 0.2
    high_delay_rate: float = 0.5
    variable_delay_std: float = 5.0
    min_lead_time_obs: int = 3
    concentrated_share: float = 0.5
    recent_window_days: int = 90

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "late_grace_days": self.late_grace_days,
            "min_shipments": self.min_shipments,
            "delayed_rate": self.delayed_rate,
            "high_delay_rate": self.high_delay_rate,
            "variable_delay_std": self.variable_delay_std,
            "min_lead_time_obs": self.min_lead_time_obs,
            "concentrated_share": self.concentrated_share,
            "recent_window_days": self.recent_window_days,
        }


DEFAULT_PROCUREMENT_CONFIG = ProcurementIntelligenceConfig()


@dataclass
class SupplierPerformance:
    """Descriptive per-supplier procurement performance (not a ranking)."""

    supplier_id: str
    supplier_name: str
    analysis_date: str
    po_count: int = 0
    po_line_count: int = 0
    ordered_quantity: float = 0.0
    received_quantity: float | None = None
    shipment_count: int = 0
    completed_shipments: int = 0
    on_time_shipments: int = 0
    late_shipments: int = 0
    on_time_rate: float | None = None
    average_delay_days: float | None = None
    median_delay_days: float | None = None
    max_delay_days: float | None = None
    average_lead_time_days: float | None = None
    median_lead_time_days: float | None = None
    min_lead_time_days: float | None = None
    max_lead_time_days: float | None = None
    lead_time_std: float | None = None
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the performance."""
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "analysis_date": self.analysis_date,
            "po_count": self.po_count,
            "po_line_count": self.po_line_count,
            "ordered_quantity": self.ordered_quantity,
            "received_quantity": self.received_quantity,
            "shipment_count": self.shipment_count,
            "completed_shipments": self.completed_shipments,
            "on_time_shipments": self.on_time_shipments,
            "late_shipments": self.late_shipments,
            "on_time_rate": self.on_time_rate,
            "average_delay_days": self.average_delay_days,
            "median_delay_days": self.median_delay_days,
            "max_delay_days": self.max_delay_days,
            "average_lead_time_days": self.average_lead_time_days,
            "median_lead_time_days": self.median_lead_time_days,
            "min_lead_time_days": self.min_lead_time_days,
            "max_lead_time_days": self.max_lead_time_days,
            "lead_time_std": self.lead_time_std,
            "missing_evidence": self.missing_evidence,
        }


@dataclass
class LeadTimeMetrics:
    """Observed vs contracted lead times for one supplier/product."""

    supplier_id: str
    product_id: str
    observations: int = 0
    average_observed_days: float | None = None
    median_observed_days: float | None = None
    min_observed_days: float | None = None
    max_observed_days: float | None = None
    std_observed_days: float | None = None
    contracted_days: float | None = None
    delay_frequency: float | None = None
    percentiles: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the lead times."""
        return {
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "observations": self.observations,
            "average_observed_days": self.average_observed_days,
            "median_observed_days": self.median_observed_days,
            "min_observed_days": self.min_observed_days,
            "max_observed_days": self.max_observed_days,
            "std_observed_days": self.std_observed_days,
            "contracted_days": self.contracted_days,
            "delay_frequency": self.delay_frequency,
            "percentiles": self.percentiles,
        }


@dataclass
class DeliveryMetrics:
    """Delivery behavior with descriptive reliability class (not a rank)."""

    supplier_id: str
    reliability: str = "UNKNOWN"  # UNKNOWN|STABLE|VARIABLE|DELAYED|HIGH_DELAY
    shipments: int = 0
    on_time: int = 0
    late: int = 0
    on_time_rate: float | None = None
    late_rate: float | None = None
    average_delay_days: float | None = None
    delay_std: float | None = None
    evidence: str = ""
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of delivery behavior."""
        return {
            "supplier_id": self.supplier_id,
            "reliability": self.reliability,
            "shipments": self.shipments,
            "on_time": self.on_time,
            "late": self.late,
            "on_time_rate": self.on_time_rate,
            "late_rate": self.late_rate,
            "average_delay_days": self.average_delay_days,
            "delay_std": self.delay_std,
            "evidence": self.evidence,
            "missing_evidence": self.missing_evidence,
        }


@dataclass
class SupplierProductMetrics:
    """Supplier-product relationship analytics with linked exposure."""

    supplier_id: str
    supplier_name: str
    product_id: str
    product_name: str = ""
    po_count: int = 0
    ordered_quantity: float = 0.0
    received_quantity: float | None = None
    shipment_count: int = 0
    observed_lead_time_days: float | None = None
    on_time_rate: float | None = None
    moq: float | None = None
    moq_compliance_rate: float | None = None
    exposed_warehouses: list[str] = field(default_factory=list)
    at_risk_warehouses: list[str] = field(default_factory=list)
    stockout_warehouses: list[str] = field(default_factory=list)
    high_uncertainty: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the relationship."""
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "po_count": self.po_count,
            "ordered_quantity": self.ordered_quantity,
            "received_quantity": self.received_quantity,
            "shipment_count": self.shipment_count,
            "observed_lead_time_days": self.observed_lead_time_days,
            "on_time_rate": self.on_time_rate,
            "moq": self.moq,
            "moq_compliance_rate": self.moq_compliance_rate,
            "exposed_warehouses": self.exposed_warehouses,
            "at_risk_warehouses": self.at_risk_warehouses,
            "stockout_warehouses": self.stockout_warehouses,
            "high_uncertainty": self.high_uncertainty,
        }


@dataclass
class OpenOrderMetrics:
    """Outstanding procurement commitments (descriptive, not a plan)."""

    po_id: str
    po_number: str
    supplier_id: str
    product_id: str
    order_date: str
    expected_arrival: str | None = None
    ordered_quantity: float = 0.0
    received_quantity: float = 0.0
    remaining_quantity: float = 0.0
    overdue: bool = False
    days_outstanding: int | None = None
    arrival_status: str = "UNKNOWN"  # expected|overdue|received|unknown

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the open order."""
        return {
            "po_id": self.po_id,
            "po_number": self.po_number,
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "order_date": self.order_date,
            "expected_arrival": self.expected_arrival,
            "ordered_quantity": self.ordered_quantity,
            "received_quantity": self.received_quantity,
            "remaining_quantity": self.remaining_quantity,
            "overdue": self.overdue,
            "days_outstanding": self.days_outstanding,
            "arrival_status": self.arrival_status,
        }


@dataclass
class InboundCoverage:
    """Inbound coverage state for one product/warehouse series."""

    product_id: str
    warehouse_id: str
    state: str = "UNKNOWN"  # INBOUND_SUPPORTED|INBOUND_PARTIAL|INBOUND_INSUFFICIENT|NO_KNOWN_INBOUND|UNKNOWN
    known_inbound: float = 0.0
    uncovered_demand: float | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of inbound coverage."""
        return {
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "state": self.state,
            "known_inbound": self.known_inbound,
            "uncovered_demand": self.uncovered_demand,
            "reason": self.reason,
        }


@dataclass
class MOQMetrics:
    """Descriptive MOQ behavior (never EOQ or optimal quantities)."""

    supplier_id: str
    product_id: str | None = None
    moq: float | None = None
    orders: int = 0
    compliant_orders: int = 0
    compliance_rate: float | None = None
    below_moq_orders: int = 0
    min_order_ratio: float | None = None
    median_order_ratio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of MOQ behavior."""
        return {
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "moq": self.moq,
            "orders": self.orders,
            "compliant_orders": self.compliant_orders,
            "compliance_rate": self.compliance_rate,
            "below_moq_orders": self.below_moq_orders,
            "min_order_ratio": self.min_order_ratio,
            "median_order_ratio": self.median_order_ratio,
        }


@dataclass
class SupplierConcentration:
    """Descriptive concentration exposure (never a diversification order)."""

    dimension: str
    supplier_id: str | None = None
    share: float | None = None
    basis: str = ""  # spend|quantity|po_count|relationships
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the concentration."""
        return {
            "dimension": self.dimension,
            "supplier_id": self.supplier_id,
            "share": self.share,
            "basis": self.basis,
            "note": self.note,
        }


@dataclass
class SupplierExposure:
    """Inventory exposure connected to one supplier (descriptive)."""

    supplier_id: str
    supplier_name: str
    affected_products: list[str] = field(default_factory=list)
    affected_warehouses: list[str] = field(default_factory=list)
    at_risk_products: list[str] = field(default_factory=list)
    stockout_products: list[str] = field(default_factory=list)
    urgent_products: list[str] = field(default_factory=list)
    high_uncertainty_products: list[str] = field(default_factory=list)
    open_po_quantity: float = 0.0
    inbound_quantity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the exposure."""
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "affected_products": self.affected_products,
            "affected_warehouses": self.affected_warehouses,
            "at_risk_products": self.at_risk_products,
            "stockout_products": self.stockout_products,
            "urgent_products": self.urgent_products,
            "high_uncertainty_products": self.high_uncertainty_products,
            "open_po_quantity": self.open_po_quantity,
            "inbound_quantity": self.inbound_quantity,
        }


@dataclass
class ProcurementRiskSignal:
    """Descriptive procurement risk signal (not a score, not a ranking)."""

    supplier_id: str | None = None
    product_id: str | None = None
    signal: str = "UNKNOWN"  # NO_SIGNAL|MONITOR|ELEVATED|HIGH_EXPOSURE|UNKNOWN
    severity: str = "unknown"
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the risk signal."""
        return {
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "signal": self.signal,
            "severity": self.severity,
            "reason": self.reason,
            "evidence": self.evidence,
            "metrics": self.metrics,
            "missing_evidence": self.missing_evidence,
        }


@dataclass
class ServiceExposure:
    """Co-occurrence of supplier delays with service exposure (no causality)."""

    supplier_id: str
    product_id: str
    warehouse_id: str
    delayed_shipments: int = 0
    service_flag: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the co-occurrence."""
        return {
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "delayed_shipments": self.delayed_shipments,
            "service_flag": self.service_flag,
            "description": self.description,
        }


@dataclass
class ProcurementIntelligenceResult:
    """Full per-supplier intelligence with traceability."""

    supplier_id: str
    supplier_name: str
    analysis_date: str
    performance: SupplierPerformance | None = None
    delivery: DeliveryMetrics | None = None
    relationships: list[SupplierProductMetrics] = field(default_factory=list)
    open_orders: list[OpenOrderMetrics] = field(default_factory=list)
    moq: list[MOQMetrics] = field(default_factory=list)
    exposure: SupplierExposure | None = None
    risk_signal: ProcurementRiskSignal | None = None
    service_impacts: list[ServiceExposure] = field(default_factory=list)
    synthetic: bool = True
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the result."""
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "analysis_date": self.analysis_date,
            "performance": self.performance.to_dict() if self.performance else None,
            "delivery": self.delivery.to_dict() if self.delivery else None,
            "relationships": [rel.to_dict() for rel in self.relationships],
            "open_orders": [order.to_dict() for order in self.open_orders],
            "moq": [row.to_dict() for row in self.moq],
            "exposure": self.exposure.to_dict() if self.exposure else None,
            "risk_signal": self.risk_signal.to_dict() if self.risk_signal else None,
            "service_impacts": [item.to_dict() for item in self.service_impacts],
            "synthetic": self.synthetic,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
        }

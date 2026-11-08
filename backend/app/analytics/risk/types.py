"""Typed risk intelligence contracts (Phase 7)."""

from dataclasses import dataclass, field
from typing import Any

SEVERITY_ORDER = ["UNKNOWN", "LOW", "MODERATE", "HIGH", "CRITICAL"]

SUPPLIER_SEVERITY_ORDER = ["UNKNOWN", "LOW", "MODERATE", "ELEVATED", "HIGH"]

PROCUREMENT_SEVERITY_ORDER = ["UNKNOWN", "NO_SIGNAL", "MONITOR", "ELEVATED", "HIGH_EXPOSURE"]

EXPOSURE_SEVERITY_ORDER = ["unknown", "no_exposure", "watch", "elevated", "immediate"]


@dataclass(frozen=True)
class RiskIntelligenceConfig:
    """Explicit thresholds for risk rules. Every threshold documented.

    - min_shipments: minimum delivered shipments for supplier evidence;
      fewer observations keep supplier risk UNKNOWN.
    - high_delay_rate / delayed_rate: late-rate cutoffs mapping to HIGH
      and ELEVATED supplier risk.
    - variable_delay_std: delay spread cutoff for variability evidence.
    - concentrated_share: top-supplier share flagging concentration
      exposure (descriptive, never a diversification order).
    - critical_dos / at_risk_dos: days-of-supply cutoffs reused for
      inventory risk banding (same meaning as Phase 5 health).
    - urgent_days / plan_days: projected-stockout urgency cutoffs reused
      for inventory risk banding.
    - wide_interval_spread: relative interval-width cutoff for HIGH
      forecast-uncertainty risk.
    - recent_window_days: window behind recent service/delay evidence.
    """

    min_shipments: int = 5
    high_delay_rate: float = 0.5
    delayed_rate: float = 0.2
    variable_delay_std: float = 5.0
    concentrated_share: float = 0.5
    critical_dos: float = 3.0
    at_risk_dos: float = 7.0
    urgent_days: int = 3
    plan_days: int = 14
    wide_interval_spread: float = 1.0
    recent_window_days: int = 90

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "min_shipments": self.min_shipments,
            "high_delay_rate": self.high_delay_rate,
            "delayed_rate": self.delayed_rate,
            "variable_delay_std": self.variable_delay_std,
            "concentrated_share": self.concentrated_share,
            "critical_dos": self.critical_dos,
            "at_risk_dos": self.at_risk_dos,
            "urgent_days": self.urgent_days,
            "plan_days": self.plan_days,
            "wide_interval_spread": self.wide_interval_spread,
            "recent_window_days": self.recent_window_days,
        }


DEFAULT_RISK_CONFIG = RiskIntelligenceConfig()


@dataclass
class RiskRecord:
    """One explainable, traceable risk record."""

    risk_id: str
    domain: str
    entity_type: str  # product_warehouse|supplier|supplier_product|warehouse
    entity_id: str
    product_id: str | None = None
    warehouse_id: str | None = None
    supplier_id: str | None = None
    analysis_date: str = ""
    state: str = "UNKNOWN"
    severity: str = "UNKNOWN"
    evidence: list[str] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)
    supporting_records: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    confidence: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)
    explanation: str = ""
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the risk record."""
        return {
            "risk_id": self.risk_id,
            "domain": self.domain,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "supplier_id": self.supplier_id,
            "analysis_date": self.analysis_date,
            "state": self.state,
            "severity": self.severity,
            "evidence": self.evidence,
            "metrics": self.metrics,
            "supporting_records": self.supporting_records,
            "missing_evidence": self.missing_evidence,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "explanation": self.explanation,
            "synthetic": self.synthetic,
        }


def risk_id(domain: str, entity_type: str, entity_id: str, analysis_date: str) -> str:
    """Build a deterministic risk identifier."""
    return f"{domain}:{entity_type}:{entity_id}:{analysis_date}"


def max_severity(states: list[str], order: list[str] = SEVERITY_ORDER) -> str:
    """Return the highest-ranked state, UNKNOWN only when all unknown."""
    known = [state for state in states if state in order and state != "UNKNOWN"]
    if not known:
        return "UNKNOWN"
    return max(known, key=order.index)

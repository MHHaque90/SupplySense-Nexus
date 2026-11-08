"""Scenario, Decision, and Optimization models for SupplySense Nexus."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class Scenario(BaseMixin, DataProvenanceMixin, Base):
    """Scenario definitions for analysis."""

    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str] = mapped_column(String(100), nullable=False, default="baseline", index=True)
    base_assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    created_by_user = relationship("User", back_populates="scenarios", lazy="selectin")
    scenario_events = relationship("ScenarioEvent", back_populates="scenario", lazy="selectin")
    scenario_results = relationship("ScenarioResult", back_populates="scenario", lazy="selectin")
    decision_options = relationship("DecisionOption", back_populates="scenario", lazy="selectin")
    decision_comparisons = relationship("DecisionComparison", back_populates="scenario", lazy="selectin")
    optimization_runs = relationship("OptimizationRun", back_populates="scenario", lazy="selectin")

    def __repr__(self) -> str:
        return f"Scenario(id={self.id}, name={self.name}, type={self.scenario_type})"


class ScenarioEvent(BaseMixin, Base):
    """Events within a scenario."""

    __tablename__ = "scenario_events"

    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    magnitude: Mapped[str] = mapped_column(String(10), nullable=False, default="0")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("products.id"), nullable=True, index=True)
    affected_warehouse_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=True, index=True)
    affected_supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True, index=True)
    probability: Mapped[str] = mapped_column(String(5), nullable=False, default="0.0")

    scenario = relationship("Scenario", back_populates="scenario_events", lazy="selectin")
    affected_product = relationship("Product", foreign_keys=[affected_product_id], back_populates="scenario_events", lazy="selectin")
    affected_warehouse = relationship("Warehouse", foreign_keys=[affected_warehouse_id], back_populates="scenario_events", lazy="selectin")
    affected_supplier = relationship("Supplier", foreign_keys=[affected_supplier_id], back_populates="scenario_events", lazy="selectin")

    def __repr__(self) -> str:
        return f"ScenarioEvent(id={self.id}, scenario_id={self.scenario_id}, type={self.event_type})"


class ScenarioResult(BaseMixin, DataProvenanceMixin, Base):
    """Computed results for scenarios."""

    __tablename__ = "scenario_results"

    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)
    decision_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False, index=True)
    expected_cost: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    expected_service_level: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    stockout_risk: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    inventory_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_exposure: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[str] = mapped_column(String(5), nullable=False, default="0")

    scenario = relationship("Scenario", back_populates="scenario_results", lazy="selectin")
    decision_option = relationship("DecisionOption", back_populates="scenario_results", lazy="selectin")

    def __repr__(self) -> str:
        return f"ScenarioResult(id={self.id}, scenario_id={self.scenario_id})"


class DecisionOption(BaseMixin, DataProvenanceMixin, Base):
    """Decision options available in the Decision Replay Lab."""

    __tablename__ = "decision_options"

    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)
    option_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_cost: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    estimated_service_level: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    estimated_stockout_risk: Mapped[str] = mapped_column(String(5), nullable=False, default="0")

    scenario = relationship("Scenario", back_populates="decision_options", lazy="selectin")
    scenario_results = relationship("ScenarioResult", back_populates="decision_option", lazy="selectin")
    decision_comparisons_baseline = relationship("DecisionComparison", foreign_keys="DecisionComparison.baseline_option_id", back_populates="baseline_option", lazy="selectin")
    decision_comparisons_alternative = relationship("DecisionComparison", foreign_keys="DecisionComparison.alternative_option_id", back_populates="alternative_option", lazy="selectin")

    def __repr__(self) -> str:
        return f"DecisionOption(id={self.id}, scenario_id={self.scenario_id}, type={self.option_type})"


class DecisionComparison(BaseMixin, DataProvenanceMixin, Base):
    """Comparison results across decision options."""

    __tablename__ = "decision_comparisons"

    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    baseline_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False)
    alternative_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_options.id"), nullable=False)
    cost_difference: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    service_difference: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    risk_difference: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    recommendation_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[str] = mapped_column(String(5), nullable=False, default="0")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    scenario = relationship("Scenario", back_populates="decision_comparisons", lazy="selectin")
    user = relationship("User", back_populates="decision_comparisons", lazy="selectin")
    baseline_option = relationship("DecisionOption", foreign_keys=[baseline_option_id], back_populates="decision_comparisons_baseline", lazy="selectin")
    alternative_option = relationship("DecisionOption", foreign_keys=[alternative_option_id], back_populates="decision_comparisons_alternative", lazy="selectin")

    def __repr__(self) -> str:
        return f"DecisionComparison(id={self.id}, scenario_id={self.scenario_id}, rank={self.recommendation_rank})"


class OptimizationRun(BaseMixin, DataProvenanceMixin, Base):
    """Records of optimization model executions."""

    __tablename__ = "optimization_runs"

    scenario_id: Mapped[str] = mapped_column(String(36), ForeignKey("scenarios.id"), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(String(100), nullable=False)
    solver_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    objective_value: Mapped[str] = mapped_column(String(15), nullable=False, default="0")
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraint_violations: Mapped[str | None] = mapped_column(Text, nullable=True)
    solver_time_seconds: Mapped[str] = mapped_column(String(10), nullable=False, default="0")

    scenario = relationship("Scenario", back_populates="optimization_runs", lazy="selectin")

    def __repr__(self) -> str:
        return f"OptimizationRun(id={self.id}, scenario_id={self.scenario_id}, status={self.solver_status})"

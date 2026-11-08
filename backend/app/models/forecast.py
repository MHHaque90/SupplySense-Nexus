"""Forecast, Disruption, and Scenario models for SupplySense Nexus."""

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class Forecast(BaseMixin, DataProvenanceMixin, Base):
    """Forecast results from model runs."""

    __tablename__ = "forecasts"

    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    forecast_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    point_estimate: Mapped[str] = mapped_column(String(12), nullable=False)
    lower_bound: Mapped[str] = mapped_column(String(12), nullable=False)
    upper_bound: Mapped[str] = mapped_column(String(12), nullable=False)
    model_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=True, index=True)
    confidence_level: Mapped[str] = mapped_column(String(5), nullable=False, default="0.95")
    forecast_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="forecasts", lazy="selectin")
    warehouse = relationship("Warehouse", back_populates="forecasts", lazy="selectin")
    model_version = relationship("ModelVersion", back_populates="forecasts", lazy="selectin")

    def __repr__(self) -> str:
        return f"Forecast(id={self.id}, product_id={self.product_id}, date={self.forecast_date})"


class ForecastRun(BaseMixin, DataProvenanceMixin, Base):
    """Metadata for forecast model runs."""

    __tablename__ = "forecast_runs"

    model_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=False, index=True)
    run_timestamp: Mapped[str] = mapped_column(Date, nullable=False)
    training_window_start: Mapped[str | None] = mapped_column(Date, nullable=True)
    training_window_end: Mapped[str | None] = mapped_column(Date, nullable=True)
    validation_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_version = relationship("ModelVersion", back_populates="forecast_runs", lazy="selectin")

    def __repr__(self) -> str:
        return f"ForecastRun(id={self.id}, model_id={self.model_version_id})"


class Disruption(BaseMixin, DataProvenanceMixin, Base):
    """Disruption event definitions."""

    __tablename__ = "disruptions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    disruption_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    start_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    affected_supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    affected_supplier = relationship("Supplier", back_populates="disruptions", lazy="selectin")
    disruption_impacts = relationship("DisruptionImpact", back_populates="disruption", lazy="selectin")

    def __repr__(self) -> str:
        return f"Disruption(id={self.id}, type={self.disruption_type}, severity={self.severity})"


class DisruptionImpact(BaseMixin, Base):
    """Computed impact of disruptions on products/warehouses."""

    __tablename__ = "disruption_impacts"

    disruption_id: Mapped[str] = mapped_column(String(36), ForeignKey("disruptions.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    estimated_demand_shortfall: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    estimated_cost_impact: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    stockout_probability: Mapped[str] = mapped_column(String(5), nullable=False, default="0")

    disruption = relationship("Disruption", back_populates="disruption_impacts", lazy="selectin")
    product = relationship("Product", back_populates="disruption_impacts", lazy="selectin")
    warehouse = relationship("Warehouse", back_populates="disruption_impacts", lazy="selectin")

    def __repr__(self) -> str:
        return f"DisruptionImpact(id={self.id}, disruption_id={self.disruption_id})"

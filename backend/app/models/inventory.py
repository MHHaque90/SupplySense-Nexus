"""Warehouse and Inventory models for SupplySense Nexus."""

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class Warehouse(BaseMixin, DataProvenanceMixin, Base):
    """Warehouse locations."""

    __tablename__ = "warehouses"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_utilization: Mapped[str] = mapped_column(String(5), nullable=False, default="0.00")
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    organization = relationship("Organization", back_populates="warehouses", lazy="selectin")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="warehouse", lazy="selectin")
    inventory_transactions = relationship("InventoryTransaction", back_populates="warehouse", lazy="selectin")
    sales_orders = relationship("SalesOrder", back_populates="warehouse", lazy="selectin")
    demand_observations = relationship("DemandObservation", back_populates="warehouse", lazy="selectin")
    forecasts = relationship("Forecast", back_populates="warehouse", lazy="selectin")
    disruption_impacts = relationship("DisruptionImpact", back_populates="warehouse", lazy="selectin")
    scenario_events = relationship("ScenarioEvent", foreign_keys="ScenarioEvent.affected_warehouse_id", back_populates="affected_warehouse", lazy="selectin")

    def __repr__(self) -> str:
        return f"Warehouse(id={self.id}, name={self.name})"


class InventorySnapshot(BaseMixin, DataProvenanceMixin, Base):
    """Point-in-time inventory position records."""

    __tablename__ = "inventory_snapshots"

    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    available_qty: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    reserved_qty: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    in_transit_qty: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    snapshot_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)

    warehouse = relationship("Warehouse", back_populates="inventory_snapshots", lazy="selectin")
    product = relationship("Product", back_populates="inventory_snapshots", lazy="selectin")

    def __repr__(self) -> str:
        return f"InventorySnapshot(id={self.id}, product_id={self.product_id}, date={self.snapshot_date})"


class InventoryTransaction(BaseMixin, DataProvenanceMixin, Base):
    """Movement history for inventory auditing."""

    __tablename__ = "inventory_transactions"

    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[str] = mapped_column(String(12), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[str] = mapped_column(Date, nullable=False, index=True)

    warehouse = relationship("Warehouse", back_populates="inventory_transactions", lazy="selectin")
    product = relationship("Product", back_populates="inventory_transactions", lazy="selectin")

    def __repr__(self) -> str:
        return f"InventoryTransaction(id={self.id}, type={self.transaction_type}, product_id={self.product_id})"

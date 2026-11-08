"""Sales, Demand, and Forecast models for SupplySense Nexus."""

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class SalesOrder(BaseMixin, DataProvenanceMixin, Base):
    """Customer order records."""

    __tablename__ = "sales_orders"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    order_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    total_amount: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    warehouse = relationship("Warehouse", back_populates="sales_orders", lazy="selectin")
    organization = relationship("Organization", back_populates="sales_orders", lazy="selectin")
    sales_order_lines = relationship("SalesOrderLine", back_populates="sales_order", lazy="selectin")

    def __repr__(self) -> str:
        return f"SalesOrder(id={self.id}, status={self.status})"


class SalesOrderLine(BaseMixin, DataProvenanceMixin, Base):
    """Individual line items in sales orders."""

    __tablename__ = "sales_order_lines"

    sales_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[str] = mapped_column(String(12), nullable=False)
    unit_price: Mapped[str] = mapped_column(String(10), nullable=False)

    sales_order = relationship("SalesOrder", back_populates="sales_order_lines", lazy="selectin")
    product = relationship("Product", back_populates="sales_order_lines", lazy="selectin")

    def __repr__(self) -> str:
        return f"SalesOrderLine(id={self.id}, product_id={self.product_id})"


class DemandObservation(BaseMixin, DataProvenanceMixin, Base):
    """Historical demand data points."""

    __tablename__ = "demand_observations"

    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[str] = mapped_column(String(12), nullable=False)

    product = relationship("Product", back_populates="demand_observations", lazy="selectin")
    warehouse = relationship("Warehouse", back_populates="demand_observations", lazy="selectin")

    __table_args__ = (
        Index("idx_demand_product_date", "product_id", "date"),
        Index("idx_demand_warehouse_date", "warehouse_id", "date"),
    )

    def __repr__(self) -> str:
        return f"DemandObservation(id={self.id}, product_id={self.product_id}, date={self.date})"

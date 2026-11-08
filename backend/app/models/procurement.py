"""Purchase Order and Shipment models for SupplySense Nexus."""

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class PurchaseOrder(BaseMixin, DataProvenanceMixin, Base):
    """Purchase order records."""

    __tablename__ = "purchase_orders"

    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    expected_delivery_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    total_cost: Mapped[str] = mapped_column(String(12), nullable=False, default="0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    supplier = relationship("Supplier", back_populates="purchase_orders", lazy="selectin")
    organization = relationship("Organization", back_populates="purchase_orders", lazy="selectin")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="purchase_order", lazy="selectin")
    shipments = relationship("Shipment", back_populates="purchase_order", lazy="selectin")

    def __repr__(self) -> str:
        return f"PurchaseOrder(id={self.id}, po_number={self.po_number}, status={self.status})"


class PurchaseOrderLine(BaseMixin, DataProvenanceMixin, Base):
    """Individual line items in purchase orders."""

    __tablename__ = "purchase_order_lines"

    po_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[str] = mapped_column(String(12), nullable=False)
    unit_cost: Mapped[str] = mapped_column(String(10), nullable=False)
    line_total: Mapped[str] = mapped_column(String(12), nullable=False, default="0")

    purchase_order = relationship("PurchaseOrder", back_populates="purchase_order_lines", lazy="selectin")
    product = relationship("Product", back_populates="purchase_order_lines", lazy="selectin")

    def __repr__(self) -> str:
        return f"PurchaseOrderLine(id={self.id}, po_id={self.po_id}, product_id={self.product_id})"


class Shipment(BaseMixin, DataProvenanceMixin, Base):
    """Shipment records."""

    __tablename__ = "shipments"

    po_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    shipped_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    expected_arrival_date: Mapped[str] = mapped_column(Date, nullable=False)
    actual_arrival_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)

    purchase_order = relationship("PurchaseOrder", back_populates="shipments", lazy="selectin")
    supplier = relationship("Supplier", back_populates="shipments", lazy="selectin")
    shipment_events = relationship("ShipmentEvent", back_populates="shipment", lazy="selectin")

    def __repr__(self) -> str:
        return f"Shipment(id={self.id}, status={self.status})"


class ShipmentEvent(BaseMixin, Base):
    """Event log for shipment tracking."""

    __tablename__ = "shipment_events"

    shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_date: Mapped[str] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    shipment = relationship("Shipment", back_populates="shipment_events", lazy="selectin")

    def __repr__(self) -> str:
        return f"ShipmentEvent(id={self.id}, type={self.event_type}, date={self.event_date})"

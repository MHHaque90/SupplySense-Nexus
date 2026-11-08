"""Supplier and Procurement models for SupplySense Nexus."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class Supplier(BaseMixin, DataProvenanceMixin, Base):
    """Supplier master data."""

    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[str] = mapped_column(String(3), nullable=True, default=None)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    organization = relationship("Organization", back_populates="suppliers", lazy="selectin")
    supplier_products = relationship("SupplierProduct", back_populates="supplier", lazy="selectin")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", lazy="selectin")
    shipments = relationship("Shipment", back_populates="supplier", lazy="selectin")
    disruptions = relationship("Disruption", back_populates="affected_supplier", lazy="selectin")
    scenario_events = relationship("ScenarioEvent", foreign_keys="ScenarioEvent.affected_supplier_id", back_populates="affected_supplier", lazy="selectin")

    def __repr__(self) -> str:
        return f"Supplier(id={self.id}, name={self.name}, country={self.country})"


class SupplierProduct(BaseMixin, DataProvenanceMixin, Base):
    """Supplier-to-product mapping with terms."""

    __tablename__ = "supplier_products"

    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    unit_cost: Mapped[str] = mapped_column(String(10), nullable=False, default="0")
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_order_qty: Mapped[str] = mapped_column(String(12), nullable=False, default="1")
    moq_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    capacity_units: Mapped[str] = mapped_column(String(12), nullable=True)

    supplier = relationship("Supplier", back_populates="supplier_products", lazy="selectin")
    product = relationship("Product", back_populates="supplier_products", lazy="selectin")

    def __repr__(self) -> str:
        return f"SupplierProduct(id={self.id}, supplier_id={self.supplier_id}, product_id={self.product_id})"

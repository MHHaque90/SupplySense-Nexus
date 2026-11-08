"""Product models for SupplySense Nexus."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class ProductCategory(BaseMixin, Base):
    """Product classification hierarchy."""

    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_categories.id"), nullable=True, index=True)

    products = relationship("Product", back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return f"ProductCategory(id={self.id}, name={self.name})"


class Product(BaseMixin, DataProvenanceMixin, Base):
    """Product master data."""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_categories.id"), nullable=True, index=True)
    unit_cost: Mapped[str | None] = mapped_column(String(10), nullable=True)
    weight_kg: Mapped[str | None] = mapped_column(String(8), nullable=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    category = relationship("ProductCategory", back_populates="products", lazy="selectin")
    organization = relationship("Organization", back_populates="products", lazy="selectin")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="product", lazy="selectin")
    inventory_transactions = relationship("InventoryTransaction", back_populates="product", lazy="selectin")
    bom_components_as_component = relationship("BOMComponent", foreign_keys="BOMComponent.component_product_id", back_populates="component_product", lazy="selectin")
    bom_as_finished = relationship("BOM", foreign_keys="BOM.product_id", back_populates="finished_product", lazy="selectin")
    demand_observations = relationship("DemandObservation", back_populates="product", lazy="selectin")
    forecasts = relationship("Forecast", back_populates="product", lazy="selectin")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="product", lazy="selectin")
    sales_order_lines = relationship("SalesOrderLine", back_populates="product", lazy="selectin")
    disruption_impacts = relationship("DisruptionImpact", back_populates="product", lazy="selectin")
    supplier_products = relationship("SupplierProduct", back_populates="product", lazy="selectin")
    scenario_events = relationship("ScenarioEvent", foreign_keys="ScenarioEvent.affected_product_id", back_populates="affected_product", lazy="selectin")

    def __repr__(self) -> str:
        return f"Product(id={self.id}, sku={self.sku}, name={self.name})"

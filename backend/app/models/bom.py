"""Bill of Materials models for SupplySense Nexus."""

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin, DataProvenanceMixin


class BOM(BaseMixin, DataProvenanceMixin, Base):
    """Define product compositions."""

    __tablename__ = "bills_of_materials"

    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_date: Mapped[str | None] = mapped_column(Date, nullable=True)

    finished_product = relationship("Product", foreign_keys=[product_id], back_populates="bom_as_finished", lazy="selectin")
    components = relationship("BOMComponent", back_populates="bom", lazy="selectin")

    def __repr__(self) -> str:
        return f"BOM(id={self.id}, product_id={self.product_id}, version={self.version})"


class BOMComponent(BaseMixin, Base):
    """Individual components within a BOM."""

    __tablename__ = "bom_components"

    bom_id: Mapped[str] = mapped_column(String(36), ForeignKey("bills_of_materials.id"), nullable=False, index=True)
    component_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[str] = mapped_column(String(12), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bom = relationship("BOM", back_populates="components", lazy="selectin")
    component_product = relationship("Product", foreign_keys=[component_product_id], back_populates="bom_components_as_component", lazy="selectin")

    def __repr__(self) -> str:
        return f"BOMComponent(id={self.id}, bom_id={self.bom_id}, component_id={self.component_product_id})"

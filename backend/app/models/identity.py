"""Organization and User models for SupplySense Nexus."""

from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.data_labels import DataSourceLabel
from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin


class Role(StrEnum):
    ANALYST = "analyst"
    PLANNER = "planner"
    MANAGER = "manager"
    EXECUTIVE = "executive"
    ADMIN = "admin"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class Organization(BaseMixin, Base):
    """Multi-tenancy support for different companies."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    data_source_label: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataSourceLabel.SYNTHETIC.value, server_default=DataSourceLabel.SYNTHETIC.value
    )

    users = relationship("User", back_populates="organization", lazy="selectin")
    products = relationship("Product", back_populates="organization", lazy="selectin")
    suppliers = relationship("Supplier", back_populates="organization", lazy="selectin")
    warehouses = relationship("Warehouse", back_populates="organization", lazy="selectin")
    purchase_orders = relationship("PurchaseOrder", back_populates="organization", lazy="selectin")
    sales_orders = relationship("SalesOrder", back_populates="organization", lazy="selectin")

    def __repr__(self) -> str:
        return f"Organization(id={self.id}, name={self.name})"


class User(BaseMixin, Base):
    """Application users with role-based access."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=Role.ANALYST.value)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization = relationship("Organization", back_populates="users")
    audit_events = relationship("AuditEvent", back_populates="user", lazy="selectin")
    decision_comparisons = relationship("DecisionComparison", back_populates="user", lazy="selectin")
    scenarios = relationship("Scenario", back_populates="created_by_user", lazy="selectin")
    model_versions = relationship("ModelVersion", back_populates="registered_by_user", lazy="selectin")

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username}, role={self.role})"

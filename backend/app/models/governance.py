"""Model Governance, Data Quality, and Audit models for SupplySense Nexus."""

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.mixins import BaseMixin


class ModelVersion(BaseMixin, Base):
    """Model registry for versioned ML and forecasting models."""

    __tablename__ = "model_versions"

    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    training_window_start: Mapped[str | None] = mapped_column(Date, nullable=True)
    training_window_end: Mapped[str | None] = mapped_column(Date, nullable=True)
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    registered_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    forecasts = relationship("Forecast", back_populates="model_version", lazy="selectin")
    forecast_runs = relationship("ForecastRun", back_populates="model_version", lazy="selectin")
    registered_by_user = relationship("User", back_populates="model_versions", lazy="selectin")

    __table_args__ = (
        Index("idx_mv_model_name_active", "model_name", "is_active"),
        Index("idx_mv_model_name_version", "model_name", "version"),
    )

    def __repr__(self) -> str:
        return f"ModelVersion(id={self.id}, name={self.model_name}, v={self.version})"


class DataQualityCheck(BaseMixin, Base):
    """Records of data quality validation runs."""

    __tablename__ = "data_quality_checks"

    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    check_rule: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_at: Mapped[str] = mapped_column(Date, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_dqc_table_checked_at", "table_name", "checked_at"),
        Index("idx_dqc_passed", "passed"),
    )

    def __repr__(self) -> str:
        return f"DataQualityCheck(id={self.id}, table={self.table_name}, passed={self.passed})"


class AuditEvent(BaseMixin, Base):
    """Immutable audit trail for all significant operations."""

    __tablename__ = "audit_events"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user = relationship("User", back_populates="audit_events", lazy="selectin")

    __table_args__ = (
        Index("idx_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"AuditEvent(id={self.id}, user_id={self.user_id}, action={self.action}, timestamp={self.timestamp})"

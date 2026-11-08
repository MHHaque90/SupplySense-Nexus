"""Base mixins for SupplySense Nexus SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.data_labels import DataSourceLabel


def _uuid() -> str:
    return str(uuid.uuid4())


class BaseMixin:
    """Common fields for all database models."""

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DataProvenanceMixin:
    """Adds data_source_label to a model."""

    data_source_label: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataSourceLabel.SYNTHETIC.value, server_default=DataSourceLabel.SYNTHETIC.value
    )

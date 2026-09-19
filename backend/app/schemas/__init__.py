"""Pydantic schemas for SupplySense Nexus."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    phase: str


class BaseSchema(BaseModel):
    """Base schema with common fields."""

    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

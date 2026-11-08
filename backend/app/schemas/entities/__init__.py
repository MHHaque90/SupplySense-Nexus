"""Pydantic schemas for SupplySense Nexus database entities."""

from datetime import datetime

from pydantic import BaseModel


class OrganizationResponse(BaseModel):
    id: str
    name: str
    industry: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: str
    organization_id: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ProductCategoryResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    category_id: str | None = None
    unit_cost: str | None = None
    weight_kg: str | None = None
    organization_id: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class WarehouseResponse(BaseModel):
    id: str
    name: str
    location: str
    capacity_units: int
    current_utilization: str
    organization_id: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SupplierResponse(BaseModel):
    id: str
    name: str
    country: str
    rating: str | None = None
    organization_id: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: str
    supplier_id: str
    po_number: str
    order_date: datetime
    expected_delivery_date: datetime | None = None
    total_cost: str
    status: str
    organization_id: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ShipmentResponse(BaseModel):
    id: str
    po_id: str
    supplier_id: str
    shipped_date: datetime | None = None
    expected_arrival_date: datetime
    actual_arrival_date: datetime | None = None
    status: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SalesOrderResponse(BaseModel):
    id: str
    customer_id: str
    order_date: datetime
    warehouse_id: str
    total_amount: str
    status: str
    organization_id: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DemandObservationResponse(BaseModel):
    id: str
    product_id: str
    warehouse_id: str
    date: datetime
    quantity: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ForecastResponse(BaseModel):
    id: str
    product_id: str
    warehouse_id: str
    forecast_date: datetime
    point_estimate: str
    lower_bound: str
    upper_bound: str
    model_version_id: str | None = None
    confidence_level: str
    forecast_horizon_days: int
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ScenarioResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    scenario_type: str
    seed: int
    created_by: str
    data_source_label: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    status: str
    database: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    database: str
    error: str | None = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int

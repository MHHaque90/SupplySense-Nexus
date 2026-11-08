"""All SQLAlchemy models for SupplySense Nexus."""

from backend.app.core.database import Base
from backend.app.models.ai import AiApproval, AiConversation, AiMessage
from backend.app.models.bom import BOM, BOMComponent
from backend.app.models.forecast import Disruption, DisruptionImpact, Forecast, ForecastRun
from backend.app.models.governance import AuditEvent, DataQualityCheck, ModelVersion
from backend.app.models.identity import Organization, Role, User
from backend.app.models.inventory import InventorySnapshot, InventoryTransaction, Warehouse
from backend.app.models.procurement import PurchaseOrder, PurchaseOrderLine, Shipment, ShipmentEvent
from backend.app.models.products import Product, ProductCategory
from backend.app.models.sales import DemandObservation, SalesOrder, SalesOrderLine
from backend.app.models.scenario import (
    DecisionComparison,
    DecisionOption,
    OptimizationRun,
    Scenario,
    ScenarioEvent,
    ScenarioResult,
)
from backend.app.models.supplier import Supplier, SupplierProduct

__all__ = [
    "Base",
    "Organization",
    "User",
    "Role",
    "ProductCategory",
    "Product",
    "BOM",
    "BOMComponent",
    "Warehouse",
    "InventorySnapshot",
    "InventoryTransaction",
    "Supplier",
    "SupplierProduct",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "Shipment",
    "ShipmentEvent",
    "SalesOrder",
    "SalesOrderLine",
    "DemandObservation",
    "Forecast",
    "ForecastRun",
    "Disruption",
    "DisruptionImpact",
    "Scenario",
    "ScenarioEvent",
    "ScenarioResult",
    "DecisionOption",
    "DecisionComparison",
    "OptimizationRun",
    "ModelVersion",
    "DataQualityCheck",
    "AuditEvent",
    "AiConversation",
    "AiMessage",
    "AiApproval",
]

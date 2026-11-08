"""Repository layer for SupplySense Nexus.

All database access goes through repositories.
Repositories provide typed access to database operations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, entity_id: str):
        """Get an entity by ID."""
        result = await self.session.get(self.model, entity_id)
        return result

    async def create(self, obj):
        """Create a new entity."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj):
        """Update an existing entity."""
        await self.session.flush()
        return obj

    async def list_all(self, limit: int = 100, offset: int = 0):
        """List all entities with pagination."""
        result = await self.session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def delete(self, obj):
        """Delete an entity."""
        await self.session.delete(obj)
        await self.session.flush()


class OrganizationRepository(BaseRepository):
    """Repository for Organization entities."""

    model = None  # Set by subclasses

    async def get_by_name(self, name: str):
        """Get organization by name."""
        result = await self.session.execute(
            select(self.model).where(self.model.name == name)
        )
        return result.scalar_one_or_none()


class UserRepository(BaseRepository):
    """Repository for User entities."""

    async def get_by_email(self, email: str):
        """Get user by email."""
        from backend.app.models.identity import User
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()


class ProductRepository(BaseRepository):
    """Repository for Product entities."""

    async def get_by_sku(self, sku: str):
        """Get product by SKU."""
        from backend.app.models.products import Product
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()


class SupplierRepository(BaseRepository):
    """Repository for Supplier entities."""

    async def get_by_name(self, name: str):
        """Get supplier by name."""
        from backend.app.models.supplier import Supplier
        result = await self.session.execute(
            select(Supplier).where(Supplier.name == name)
        )
        return result.scalar_one_or_none()


class WarehouseRepository(BaseRepository):
    """Repository for Warehouse entities."""

    async def get_by_name(self, name: str):
        """Get warehouse by name."""
        from backend.app.models.inventory import Warehouse
        result = await self.session.execute(
            select(Warehouse).where(Warehouse.name == name)
        )
        return result.scalar_one_or_none()


class InventoryRepository(BaseRepository):
    """Repository for Inventory entities."""

    async def get_current_position(self, warehouse_id: str, product_id: str):
        """Get current inventory position."""
        from backend.app.models.inventory import InventorySnapshot
        result = await self.session.execute(
            select(InventorySnapshot).where(
                InventorySnapshot.warehouse_id == warehouse_id,
                InventorySnapshot.product_id == product_id,
            ).order_by(InventorySnapshot.snapshot_date.desc())
        )
        return result.scalar_one_or_none()


class PurchaseOrderRepository(BaseRepository):
    """Repository for PurchaseOrder entities."""

    async def get_by_po_number(self, po_number: str):
        """Get purchase order by PO number."""
        from backend.app.models.procurement import PurchaseOrder
        result = await self.session.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )
        return result.scalar_one_or_none()


class ShipmentRepository(BaseRepository):
    """Repository for Shipment entities."""

    async def get_by_status(self, status: str):
        """Get shipments by status."""
        from backend.app.models.procurement import Shipment
        result = await self.session.execute(
            select(Shipment).where(Shipment.status == status)
        )
        return result.scalars().all()


class ScenarioRepository(BaseRepository):
    """Repository for Scenario entities."""

    async def get_by_name(self, name: str):
        """Get scenario by name."""
        from backend.app.models.scenario import Scenario
        result = await self.session.execute(
            select(Scenario).where(Scenario.name == name)
        )
        return result.scalar_one_or_none()


class AuditRepository(BaseRepository):
    """Repository for AuditEvent entities."""

    async def get_by_user(self, user_id: str, limit: int = 100):
        """Get audit events by user."""
        from backend.app.models.governance import AuditEvent
        result = await self.session.execute(
            select(AuditEvent).where(AuditEvent.user_id == user_id)
            .order_by(AuditEvent.timestamp.desc())
            .offset(0).limit(limit)
        )
        return result.scalars().all()

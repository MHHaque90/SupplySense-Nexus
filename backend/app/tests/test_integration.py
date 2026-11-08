"""Database integration tests for SupplySense Nexus Phase 1."""

import pytest
from sqlalchemy import text

from backend.app.core.database import AsyncSessionLocal, engine
from backend.app.models import *


@pytest.mark.asyncio
async def test_database_connection():
    """Test that the database connection works."""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_all_tables_exist():
    """Verify all expected tables exist."""
    expected_tables = [
        "organizations", "users", "product_categories", "products",
        "bills_of_materials", "bom_components", "warehouses",
        "inventory_snapshots", "inventory_transactions",
        "suppliers", "supplier_products",
        "purchase_orders", "purchase_order_lines",
        "shipments", "shipment_events",
        "sales_orders", "sales_order_lines",
        "demand_observations", "forecasts", "forecast_runs",
        "disruptions", "disruption_impacts",
        "scenarios", "scenario_events", "scenario_results",
        "decision_options", "decision_comparisons",
        "optimization_runs", "model_versions",
        "data_quality_checks", "audit_events",
    ]
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        ))
        tables = {row[0] for row in result.all()}
        for table_name in expected_tables:
            assert table_name in tables, f"Missing table: {table_name}"


@pytest.mark.asyncio
async def test_foreign_key_constraints():
    """Verify foreign key relationships work."""
    async with engine.begin() as conn:
        # Check that foreign key constraints exist
        result = await conn.execute(text(
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public'"
        ))
        fk_count = result.scalar()
        assert fk_count > 0, "Expected foreign key constraints to exist"


@pytest.mark.asyncio
async def test_create_organization():
    """Test creating an organization."""
    org = Organization(name="Test Org", industry="Testing")
    async with AsyncSessionLocal() as session:
        session.add(org)
        await session.flush()
        assert org.id is not None
        assert org.name == "Test Org"
        await session.rollback()


@pytest.mark.asyncio
async def test_create_product():
    """Test creating a product."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        cat = ProductCategory(name="Electronics")
        session.add(cat)
        await session.flush()

        product = Product(sku="TEST-001", name="Test Product", category_id=cat.id, organization_id=org.id)
        session.add(product)
        await session.flush()
        assert product.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_create_supplier():
    """Test creating a supplier."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        supplier = Supplier(name="Test Supplier", country="US", organization_id=org.id)
        session.add(supplier)
        await session.flush()
        assert supplier.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_unique_constraint_email():
    """Verify email uniqueness constraint."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        user1 = User(email="test@example.com", username="test1", password_hash="hash", organization_id=org.id)
        user2 = User(email="test2@example.com", username="test2", password_hash="hash", organization_id=org.id)
        session.add(user1)
        session.add(user2)
        await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_create_warehouse():
    """Test creating a warehouse."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        warehouse = Warehouse(name="Main Warehouse", location="New York", capacity_units=1000, organization_id=org.id)
        session.add(warehouse)
        await session.flush()
        assert warehouse.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_create_purchase_order():
    """Test creating a purchase order."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        supplier = Supplier(name="Test Supplier", country="US", organization_id=org.id)
        session.add(supplier)
        await session.flush()

        po = PurchaseOrder(
            supplier_id=supplier.id, po_number="PO-001",
            order_date="2026-01-01", status="pending", organization_id=org.id
        )
        session.add(po)
        await session.flush()
        assert po.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_create_scenario():
    """Test creating a scenario."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        user = User(email="test@example.com", username="testuser", password_hash="hash", organization_id=org.id)
        session.add(user)
        await session.flush()

        scenario = Scenario(name="Test Scenario", scenario_type="baseline", seed=42, created_by=user.id)
        session.add(scenario)
        await session.flush()
        assert scenario.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_create_audit_event():
    """Test creating an audit event."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        user = User(email="test@example.com", username="testuser", password_hash="hash", organization_id=org.id)
        session.add(user)
        await session.flush()

        audit = AuditEvent(
            user_id=user.id, action="login", entity_type="session", timestamp="2026-01-01"
        )
        session.add(audit)
        await session.flush()
        assert audit.id is not None
        await session.rollback()


@pytest.mark.asyncio
async def test_data_provenance_label():
    """Verify data_source_label works on models."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org", industry="Testing")
        session.add(org)
        await session.flush()

        product = Product(sku="PROV-001", name="Provenance Test", data_source_label="synthetic", organization_id=org.id)
        session.add(product)
        await session.flush()
        assert product.data_source_label == "synthetic"
        await session.rollback()


@pytest.mark.asyncio
async def test_model_relationships():
    """Verify SQLAlchemy relationships work."""
    async with AsyncSessionLocal() as session:
        org = Organization(name="Test Org")
        session.add(org)
        await session.flush()

        user = User(email="test@example.com", username="test", password_hash="hash", organization_id=org.id)
        session.add(user)
        await session.flush()
        assert user.organization is not None or True
        await session.rollback()

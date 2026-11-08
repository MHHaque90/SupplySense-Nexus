"""Shared test fixtures and configuration."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base, get_db
from backend.app.core.security import hash_api_key
from backend.app.main import app
from backend.app.models import Organization, User

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/supplysense_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def test_db_session() -> AsyncSession:
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def client():
    """Provide a test client for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def ai_client():
    """ASGI test client sharing the pytest loop, with DB dependency override."""
    from backend.app.core.database import get_db as real_get_db

    async def _override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[real_get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


async def seed_api_user(
    session: AsyncSession,
    organization_id: str,
    role: str,
    raw_key: str,
    *,
    active: bool = True,
) -> User:
    """Create one synthetic user carrying a hashed API key (never the raw)."""
    user = User(
        email=f"{role}-{raw_key[-8:]}@synthetic.test",
        username=f"{role}-{raw_key[-8:]}",
        password_hash=f"hashed:synthetic-test-only:{raw_key}",
        api_key_hash=hash_api_key(raw_key),
        role=role,
        organization_id=organization_id,
        is_active=active,
    )
    session.add(user)
    await session.flush()
    return user


async def first_organization_id(session: AsyncSession) -> str:
    """Return the id of the first organization in the test database."""
    row = (
        await session.execute(select(Organization.id).order_by(Organization.created_at))
    ).scalars().first()
    assert row, "expected at least one organization"
    return row


async def load_tiny_dataset(session: AsyncSession, seed: int = 11) -> None:
    """Generate and load a small synthetic dataset (one organization)."""
    from backend.app.data.config import GenerationConfig
    from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset

    config = GenerationConfig(
        seed=seed, product_count=4, supplier_count=2, warehouse_count=1, history_days=120
    )
    dataset = generate_dataset(config)
    await load_dataset(session, dataset)
    await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create test tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

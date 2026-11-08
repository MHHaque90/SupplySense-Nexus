"""Database configuration and async engine for SupplySense Nexus."""

import asyncio
import sys

try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except AttributeError:
    pass  # Non-Windows platforms

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_recycle=settings.POOL_RECYCLE,
    pool_pre_ping=settings.POOL_PRE_PING,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency to get a database session.

    Provides a transactional session that is automatically rolled back
    on failure and always closed after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables.

    This is primarily used for testing and fallback.
    In production, Alembic migrations should be used.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose the engine and close all connections."""
    await engine.dispose()


def run_async(coro):
    """Run a coroutine with the correct event loop policy for Windows.

    Uses SelectorEventLoop on Windows to avoid ProactorEventLoop incompatibility
    with psycopg async driver.
    """
    if sys.platform == "win32":
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coro)

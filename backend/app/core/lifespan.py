"""Environment setup and utilities for SupplySense Nexus."""


from backend.app.core.database import dispose_engine, init_db


async def lifespan(app):
    """FastAPI lifespan handler for startup and shutdown."""
    await init_db()
    yield
    await dispose_engine()

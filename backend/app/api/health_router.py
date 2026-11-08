"""Health check endpoints for SupplySense Nexus."""

from fastapi import APIRouter

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal

router = APIRouter()


@router.get("/health")
async def read_health():
    """Application health check."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "Phase 1",
    }


@router.get("/health/live")
async def read_live():
    """Liveness probe - confirms the process is alive."""
    return {"status": "alive"}


@router.get("/health/ready")
async def read_ready():
    """Readiness probe - verifies PostgreSQL connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
            await session.commit()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": "disconnected", "error": str(e)}

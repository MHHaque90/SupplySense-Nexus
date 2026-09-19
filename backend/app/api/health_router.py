"""Health check endpoints for SupplySense Nexus."""

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter()


@router.get("/health")
async def read_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "Phase 0",
    }


@router.get("/health/live")
async def read_live():
    """Liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def read_ready():
    """Readiness probe."""
    return {"status": "ready"}

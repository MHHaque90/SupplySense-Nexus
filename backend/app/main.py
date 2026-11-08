"""SupplySense Nexus main application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.ai_router import router as ai_router
from backend.app.api.auth_router import router as auth_router
from backend.app.api.dashboard_router import router as dashboard_router
from backend.app.api.forecast_router import router as forecast_router
from backend.app.api.health_router import router as health_router
from backend.app.api.inventory_router import router as inventory_router
from backend.app.api.optimization_router import router as optimization_router
from backend.app.api.procurement_router import router as procurement_router
from backend.app.api.replay_router import router as replay_router
from backend.app.api.risk_router import router as risk_router
from backend.app.api.simulation_router import router as simulation_router
from backend.app.api.supplier_router import router as supplier_router
from backend.app.core.config import settings
from backend.app.core.errors import register_error_handlers
from backend.app.core.lifespan import lifespan

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Supply Chain Resilience and Decision Intelligence Platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(ai_router, prefix="/api/v1", tags=["ai"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
app.include_router(forecast_router, prefix="/api/v1", tags=["forecast"])
app.include_router(inventory_router, prefix="/api/v1", tags=["inventory"])
app.include_router(supplier_router, prefix="/api/v1", tags=["suppliers"])
app.include_router(procurement_router, prefix="/api/v1", tags=["procurement"])
app.include_router(risk_router, prefix="/api/v1", tags=["risk"])
app.include_router(simulation_router, prefix="/api/v1", tags=["simulation"])
app.include_router(replay_router, prefix="/api/v1", tags=["replay"])
app.include_router(optimization_router, prefix="/api/v1", tags=["optimization"])

register_error_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

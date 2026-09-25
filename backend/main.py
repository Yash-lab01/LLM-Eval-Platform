"""FastAPI Main Application Entrypoint.

Configures lifespan events, CORS middleware, API routes, and system health checks.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.eval import router as eval_router
from backend.api.routes.leaderboard import router as leaderboard_router
from backend.api.routes.websocket import router as websocket_router
from backend.core.config import settings
from backend.core.database import check_db_health, engine
from backend.core.redis_client import check_redis_health, close_redis
from backend.services.observability import setup_observability
from backend.services.scoring import close_scoring_models, init_scoring_models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Initializing LLM Eval Platform services...")
    # Startup checks
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    init_scoring_models()
    setup_observability()
    logger.info(f"Service health on startup: DB={db_ok}, Redis={redis_ok}")

    yield

    # Shutdown cleanup
    logger.info("Shutting down LLM Eval Platform services...")
    close_scoring_models()
    await close_redis()
    await engine.dispose()
    logger.info("All connections closed cleanly.")


app = FastAPI(
    title="LLM Eval Platform",
    description="Modular, self-hosted LLM evaluation and benchmarking platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else ["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(eval_router, prefix="/api/v1")
app.include_router(leaderboard_router, prefix="/api/v1")
app.include_router(websocket_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Comprehensive health check endpoint verifying database and Redis connectivity."""
    db_status = await check_db_health()
    redis_status = await check_redis_health()
    all_healthy = db_status and redis_status

    return {
        "status": "healthy" if all_healthy else "degraded",
        "environment": settings.environment,
        "service": "llm-eval-api",
        "components": {
            "database": "connected" if db_status else "disconnected",
            "redis": "connected" if redis_status else "disconnected",
        },
    }

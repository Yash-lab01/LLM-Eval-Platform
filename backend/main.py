"""FastAPI Main Application Entrypoint.

Configures lifespan events, CORS middleware, and core endpoints.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    # Startup: resources, connections, singletons
    yield
    # Shutdown: clean close of connections


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


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service liveness."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "service": "llm-eval-api",
    }

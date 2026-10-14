"""FastAPI gateway for AEGIS Financial Crime Intelligence Platform."""

from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes.ingestion import router as ingestion_router
from packages.domain.database import close_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database lifecycle and resources."""
    # Startup: ensure tables exist
    await init_db()
    yield
    # Shutdown: gracefully close connection pools
    await close_engine()


app = FastAPI(
    title="AEGIS — Financial Crime Intelligence API",
    description=(
        "Evidence-first AML/KYC platform combining deterministic controls, "
        "calibrated risk scoring, temporal graph intelligence, and bounded LangGraph copilots."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend / developer tooling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route mounting
app.include_router(ingestion_router)


@app.get("/healthz", tags=["System"])
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "aegis-api"}


@app.get("/livez", tags=["System"])
async def livez() -> dict[str, str]:
    """Readiness probe."""
    return {"status": "ready", "service": "aegis-api"}


@app.get("/", tags=["System"])
async def root() -> dict[str, Any]:
    """API Root metadata."""
    return {
        "service": "AEGIS Financial Crime Intelligence Platform",
        "version": "0.1.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }

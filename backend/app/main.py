"""FastAPI application entry point."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    dashboard,
    health,
    builds,
    risk,
    integrations,
    pipeline,
    settings,
    logs,
    notifications,
    users,
)
from app.services.mock_seed import seed_database

logger = logging.getLogger(__name__)

# Seed database with mock data (no-op if data already exists)
try:
    seed_database()
except Exception as exc:  # pragma: no cover - best effort seed
    logger.warning("Skipping mock data seeding: %s", exc)

app = FastAPI(
    title="Build Risk Assessment API",
    description="API for assessing CI/CD build risks using Bayesian CNN",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(builds.router, prefix="/api/builds", tags=["Builds"])
app.include_router(risk.router, prefix="/api/risk", tags=["Risk Assessment"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(integrations.router, prefix="/api", tags=["Integrations"])
app.include_router(pipeline.router, prefix="/api", tags=["Pipeline"])
app.include_router(settings.router, prefix="/api", tags=["Settings"])
app.include_router(logs.router, prefix="/api", tags=["Logging"])
app.include_router(notifications.router, prefix="/api", tags=["Notifications"])
app.include_router(users.router, prefix="/api", tags=["Users"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Build Risk Assessment API",
        "version": "1.0.0",
        "docs": "/api/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

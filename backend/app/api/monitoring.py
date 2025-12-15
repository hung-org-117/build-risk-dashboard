"""
Monitoring API - Endpoints for system monitoring and observability.

Endpoints:
- GET /monitoring/system - System stats (Celery, Redis, MongoDB)
- GET /monitoring/pipeline-runs - Recent pipeline runs
- GET /monitoring/jobs - Active background jobs
- GET /monitoring/queues - Celery queue details
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/system")
def get_system_stats(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get comprehensive system statistics.

    Returns stats for:
    - Celery workers and queues
    - Redis server
    - MongoDB server
    """
    service = MonitoringService(db)
    return service.get_system_stats()


@router.get("/pipeline-runs")
def get_pipeline_runs(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get recent pipeline runs with pagination.

    Shows pipeline execution history with status and metrics.
    """
    service = MonitoringService(db)
    return service.get_pipeline_runs(limit=limit, skip=skip, status=status)


@router.get("/jobs")
def get_background_jobs(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get active background jobs overview.

    Returns:
    - Active export jobs
    - Active scans (SonarQube, Trivy)
    - Active enrichment jobs
    """
    service = MonitoringService(db)
    return service.get_background_jobs()


@router.get("/queues")
def get_queue_stats(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get detailed Celery queue statistics.

    Shows message counts for each queue.
    """
    service = MonitoringService(db)
    stats = service.get_system_stats()
    return {
        "queues": stats.get("celery", {}).get("queues", {}),
        "workers": stats.get("celery", {}).get("workers", []),
    }

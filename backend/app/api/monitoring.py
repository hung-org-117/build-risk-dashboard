"""
Monitoring API - Endpoints for system monitoring and observability.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.middleware.rbac import Permission, RequirePermission
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/system")
def get_system_stats(
    db: Database = Depends(get_db),
    _admin: dict = Depends(RequirePermission(Permission.ADMIN_FULL)),
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


@router.get("/logs")
def get_system_logs(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    level: Optional[str] = Query(
        None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    source: Optional[str] = Query(None, description="Filter by source/component"),
    db: Database = Depends(get_db),
    _admin: dict = Depends(RequirePermission(Permission.ADMIN_FULL)),
):
    """
    Get system logs with pagination and filtering.

    Admin only. Returns logs stored in MongoDB from the application.
    """
    service = MonitoringService(db)
    return service.get_system_logs(limit=limit, skip=skip, level=level, source=source)


@router.get("/metrics")
def get_log_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back (max 7 days)"),
    bucket_minutes: int = Query(
        60, ge=15, le=360, description="Bucket size in minutes"
    ),
    db: Database = Depends(get_db),
    _admin: dict = Depends(RequirePermission(Permission.ADMIN_FULL)),
):
    """
    Get log metrics aggregated by time bucket for charts.

    Returns time-series data of log counts by level, suitable for
    visualizing error rate trends on the monitoring dashboard.
    """
    service = MonitoringService(db)
    return service.get_log_metrics(hours=hours, bucket_minutes=bucket_minutes)

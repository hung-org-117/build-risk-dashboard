"""
Enrichment Logs API - Endpoints for viewing pipeline run and audit logs.

Follows layered architecture: API -> Service -> Repository
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos.enrichment_logs import (
    AuditLogListResponse,
    FeatureAuditLogResponse,
    PipelineRunResponse,
)
from app.middleware.rbac import Permission, RequirePermission
from app.services.enrichment_logs_service import EnrichmentLogsService

router = APIRouter(
    prefix="/datasets/{dataset_id}/versions/{version_id}",
    tags=["Enrichment Logs"],
)


@router.get("/pipeline-run", response_model=Optional[PipelineRunResponse])
async def get_version_pipeline_run(
    dataset_id: str,
    version_id: str,
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get the pipeline run record for a dataset version.

    Returns the high-level pipeline execution status including:
    - Overall status and duration
    - Phase-by-phase progress
    - Error summaries
    """
    enrichment_logs_service = EnrichmentLogsService(db)
    return enrichment_logs_service.get_version_pipeline_run(
        dataset_id=dataset_id,
        version_id=version_id,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_version_audit_logs(
    dataset_id: str,
    version_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get paginated audit logs for a dataset version.

    Returns per-build execution details including:
    - Node-level execution results
    - Features extracted per node
    - Resource usage information
    - Errors and warnings
    """
    enrichment_logs_service = EnrichmentLogsService(db)
    return enrichment_logs_service.get_version_audit_logs(
        dataset_id=dataset_id,
        version_id=version_id,
        skip=skip,
        limit=limit,
        status=status,
    )


@router.get("/builds/{build_id}/audit-log", response_model=FeatureAuditLogResponse)
async def get_build_audit_log(
    dataset_id: str,
    version_id: str,
    build_id: str,
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get audit log for a specific enrichment build.

    Returns detailed node-by-node execution results for debugging.
    """
    enrichment_logs_service = EnrichmentLogsService(db)
    return enrichment_logs_service.get_build_audit_log(
        dataset_id=dataset_id,
        version_id=version_id,
        build_id=build_id,
    )

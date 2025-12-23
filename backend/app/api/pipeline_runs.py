"""
Pipeline Runs API - Query pipeline execution history.

Provides endpoints to:
- List pipeline runs with filtering by dataset_id, version_id, repo_id, pipeline_type
- Get details of a specific pipeline run by correlation_id
- Get recent pipeline runs for dashboard
"""

from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.database.mongo import get_db
from app.entities.pipeline_run import PipelineRun, PipelineStatus, PipelineType
from app.middleware.rbac import Permission, RequirePermission
from app.repositories.pipeline_run_repository import PipelineRunRepository

router = APIRouter(prefix="/pipeline-runs", tags=["Pipeline Runs"])

# Permission dependency - VIEW_DASHBOARD covers pipeline monitoring
require_view_pipelines = RequirePermission(Permission.VIEW_DASHBOARD)


@router.get("")
async def list_pipeline_runs(
    dataset_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    repo_id: Optional[str] = Query(None),
    pipeline_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    skip: int = Query(0),
    db=Depends(get_db),
    _=Depends(require_view_pipelines),
):
    """
    List pipeline runs with optional filtering.

    Filters:
    - dataset_id: Filter by dataset ObjectId
    - version_id: Filter by version ObjectId
    - repo_id: Filter by repository config ObjectId
    - pipeline_type: Filter by type (dataset_validation, dataset_enrichment, etc.)
    - status: Filter by status (running, completed, failed, etc.)
    """
    repo = PipelineRunRepository(db)

    # Build query
    query = {}
    if dataset_id:
        query["dataset_id"] = ObjectId(dataset_id)
    if version_id:
        query["version_id"] = ObjectId(version_id)
    if repo_id:
        query["repo_config_id"] = ObjectId(repo_id)
    if pipeline_type:
        query["pipeline_type"] = pipeline_type
    if status:
        query["status"] = status

    # Find with pagination
    pipeline_runs = repo.find_many(query, limit=limit, skip=skip)
    total = repo.count(query)

    return {
        "items": [_format_pipeline_run(pr) for pr in pipeline_runs],
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.get("/recent")
async def get_recent_pipeline_runs(
    limit: int = Query(10, le=50),
    db=Depends(get_db),
    _=Depends(require_view_pipelines),
):
    """Get recent pipeline runs across all types for dashboard."""
    repo = PipelineRunRepository(db)
    pipeline_runs = repo.find_many({}, limit=limit, skip=0)

    return {"items": [_format_pipeline_run(pr) for pr in pipeline_runs]}


@router.get("/{correlation_id}")
async def get_pipeline_run(
    correlation_id: str,
    db=Depends(get_db),
    _=Depends(require_view_pipelines),
):
    """Get a specific pipeline run by correlation_id."""
    repo = PipelineRunRepository(db)
    pipeline_run = repo.find_by_correlation_id(correlation_id)

    if not pipeline_run:
        return {"error": "Pipeline run not found"}

    return _format_pipeline_run(pipeline_run)


@router.get("/by-dataset/{dataset_id}")
async def get_pipeline_runs_by_dataset(
    dataset_id: str,
    limit: int = Query(20, le=100),
    db=Depends(get_db),
    _=Depends(require_view_pipelines),
):
    """Get all pipeline runs for a specific dataset."""
    repo = PipelineRunRepository(db)
    pipeline_runs = repo.find_by_dataset(dataset_id, limit=limit)

    return {"items": [_format_pipeline_run(pr) for pr in pipeline_runs]}


@router.get("/by-version/{version_id}")
async def get_pipeline_runs_by_version(
    version_id: str,
    limit: int = Query(20, le=100),
    db=Depends(get_db),
    _=Depends(require_view_pipelines),
):
    """Get all pipeline runs for a specific version."""
    repo = PipelineRunRepository(db)
    pipeline_runs = repo.find_by_version(version_id, limit=limit)

    return {"items": [_format_pipeline_run(pr) for pr in pipeline_runs]}


def _format_pipeline_run(pr: PipelineRun) -> dict:
    """Format PipelineRun for API response."""
    return {
        "correlation_id": pr.correlation_id,
        "pipeline_type": pr.pipeline_type.value
        if isinstance(pr.pipeline_type, PipelineType)
        else pr.pipeline_type,
        "status": pr.status.value if isinstance(pr.status, PipelineStatus) else pr.status,
        "dataset_id": str(pr.dataset_id) if pr.dataset_id else None,
        "version_id": str(pr.version_id) if pr.version_id else None,
        "repo_config_id": str(pr.repo_config_id) if pr.repo_config_id else None,
        "triggered_by": pr.triggered_by,
        "started_at": pr.started_at.isoformat() if pr.started_at else None,
        "completed_at": pr.completed_at.isoformat() if pr.completed_at else None,
        "duration_seconds": pr.duration_seconds,
        "progress": pr.progress,
        "phases": pr.phases,
        "result_summary": pr.result_summary,
        "error_message": pr.error_message,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
    }

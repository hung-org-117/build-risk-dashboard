"""
Training Dataset Export API endpoints.

Handles CRUD operations and generation for dataset exports.
Supports multiple exports per scenario with different configurations.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.database.mongo import Database, get_db
from app.dtos.training_export import (
    ExportCreateDTO,
    ExportListResponse,
    ExportResponse,
    SplitResponse,
)
from app.entities.user import User
from app.middleware.auth import get_current_user
from app.services.training_export_service import TrainingExportService

router = APIRouter()


@router.get("/{scenario_id}/exports", response_model=ExportListResponse)
def list_exports(
    scenario_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> ExportListResponse:
    """List all exports for a scenario."""
    service = TrainingExportService(db)
    exports, total = service.list_exports(scenario_id, skip=skip, limit=limit)

    return ExportListResponse(
        items=exports,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/{scenario_id}/exports", response_model=ExportResponse)
def create_export(
    scenario_id: str,
    dto: ExportCreateDTO,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> ExportResponse:
    """Create a new export for a scenario."""
    service = TrainingExportService(db)
    return service.create_export(scenario_id, str(current_user["_id"]), dto)


@router.get("/{scenario_id}/exports/{export_id}", response_model=ExportResponse)
def get_export(
    scenario_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> ExportResponse:
    """Get export details."""
    service = TrainingExportService(db)
    return service.get_export(scenario_id, export_id)


@router.delete("/{scenario_id}/exports/{export_id}")
def delete_export(
    scenario_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> Dict[str, bool]:
    """Delete an export and its splits."""
    service = TrainingExportService(db)
    service.delete_export(scenario_id, export_id)
    return {"deleted": True}


@router.post("/{scenario_id}/exports/{export_id}/generate")
def generate_export(
    scenario_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> Dict[str, Any]:
    """Generate dataset for an export."""
    service = TrainingExportService(db)
    return service.generate_export(scenario_id, export_id, str(current_user["_id"]))


@router.get("/{scenario_id}/exports/{export_id}/splits")
def get_export_splits(
    scenario_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> List[SplitResponse]:
    """Get all splits for an export."""
    service = TrainingExportService(db)
    return service.get_export_splits(scenario_id, export_id)


@router.get("/{scenario_id}/exports/{export_id}/splits/{split_id}/download")
def download_split(
    scenario_id: str,
    export_id: str,
    split_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Download a specific split file."""
    service = TrainingExportService(db)
    return service.download_split(scenario_id, export_id, split_id)

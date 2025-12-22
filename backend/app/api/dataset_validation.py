"""Dataset validation API endpoints."""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos.dataset_validation import (
    RepoScanConfigRequest,
    RepoValidationResult,
    StartValidationResponse,
    ValidationStatusResponse,
    ValidationSummaryResponse,
)
from app.entities.dataset_repo_stats import RepoScanConfig
from app.repositories.dataset_repo_stats import DatasetRepoStatsRepository
from app.services.dataset_validation_service import DatasetValidationService

router = APIRouter(prefix="/datasets", tags=["dataset-validation"])


@router.post("/{dataset_id}/validate", response_model=StartValidationResponse)
async def start_validation(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Start async validation of builds in a dataset."""
    service = DatasetValidationService(db)
    result = await service.start_validation(dataset_id)
    return StartValidationResponse(**result)


@router.get("/{dataset_id}/validation-status", response_model=ValidationStatusResponse)
async def get_validation_status(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Get current validation progress and status."""
    service = DatasetValidationService(db)
    result = service.get_validation_status(dataset_id)
    return ValidationStatusResponse(**result)


@router.delete("/{dataset_id}/validation")
async def cancel_validation(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Cancel ongoing validation."""
    service = DatasetValidationService(db)
    return await service.cancel_validation(dataset_id)


@router.get("/{dataset_id}/validation-summary", response_model=ValidationSummaryResponse)
async def get_validation_summary(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Get detailed validation summary including repo breakdown."""
    service = DatasetValidationService(db)
    result = service.get_validation_summary(dataset_id)
    return ValidationSummaryResponse(
        dataset_id=result["dataset_id"],
        status=result["status"],
        stats=result["stats"],
        repos=[RepoValidationResult(**r) for r in result["repos"]],
    )


@router.get("/{dataset_id}/repos")
async def list_dataset_repos(
    dataset_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    db: Database = Depends(get_db),
):
    """List repositories in a dataset (paginated)."""
    service = DatasetValidationService(db)
    return service.get_dataset_repos(
        dataset_id,
        skip=skip,
        limit=limit,
        search=q,
    )


@router.post("/{dataset_id}/reset-validation")
async def reset_validation(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Reset validation state and delete build records to allow re-validation."""
    service = DatasetValidationService(db)
    return await service.reset_validation(dataset_id)


@router.post("/{dataset_id}/reset-step2")
async def reset_step2(
    dataset_id: str,
    db: Database = Depends(get_db),
):
    """Reset Step 2 data - delete repos and build records when going back to Step 1."""
    service = DatasetValidationService(db)
    return await service.reset_step2(dataset_id)


@router.patch("/{dataset_id}/repos/{repo_id}/scan-config")
async def update_repo_scan_config(
    dataset_id: str,
    repo_id: str,
    payload: RepoScanConfigRequest,
    db: Database = Depends(get_db),
):
    """Update custom scan configuration for a specific repository."""
    repo_stats_repo = DatasetRepoStatsRepository(db)

    # Build scan config or set to None if empty
    scan_config = None
    if payload.sonarqube_properties or payload.trivy_yaml:
        scan_config = RepoScanConfig(
            sonarqube_properties=payload.sonarqube_properties,
            trivy_yaml=payload.trivy_yaml,
        )

    # Update the repo stats
    updated = repo_stats_repo.find_one_and_update(
        query={"_id": repo_stats_repo._to_object_id(repo_id)},
        update={"$set": {"scan_config": scan_config.model_dump() if scan_config else None}},
    )

    if not updated:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Repository not found")

    return {
        "message": "Scan config updated",
        "has_custom_config": scan_config is not None,
    }


@router.get("/{dataset_id}/repos/{repo_id}/scan-config")
async def get_repo_scan_config(
    dataset_id: str,
    repo_id: str,
    db: Database = Depends(get_db),
):
    """Get custom scan configuration for a specific repository."""
    repo_stats_repo = DatasetRepoStatsRepository(db)
    repo_stats = repo_stats_repo.find_by_id(repo_id)

    if not repo_stats:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Repository not found")

    return {
        "repo_id": repo_id,
        "full_name": repo_stats.full_name,
        "scan_config": repo_stats.scan_config.model_dump() if repo_stats.scan_config else None,
    }

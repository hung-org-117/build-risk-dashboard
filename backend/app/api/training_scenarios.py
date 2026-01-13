from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.database.mongo import Database, get_db
from app.dtos.training_scenario import (
    TrainingScenarioCreateDTO,
    TrainingScenarioListResponse,
    TrainingScenarioResponse,
    TrainingScenarioUpdateDTO,
)
from app.entities.training_scenario import ScenarioStatus
from app.entities.user import User
from app.middleware.auth import get_current_user
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.services.training_ingestion_service import TrainingIngestionService
from app.services.training_processing_service import TrainingProcessingService
from app.services.training_scenario_service import TrainingScenarioService

router = APIRouter()


# ============================================================================
# Preview Builds (Wizard Step 1)
# ============================================================================


@router.get("/preview-builds")
def preview_builds(
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
    languages: Optional[str] = Query(None, description="Comma-separated languages"),
    conclusions: Optional[str] = Query(
        None, description="Comma-separated conclusions (success,failure)"
    ),
    ci_provider: Optional[str] = Query(None, description="CI provider filter"),
    skip: int = 0,
    limit: int = 20,
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Preview builds matching filter criteria.

    Used by Training Scenario wizard to preview available builds before creating a scenario.
    Returns paginated builds and aggregate stats.
    """
    raw_build_run_repo = RawBuildRunRepository(db)

    # Parse comma-separated values
    conclusions_list = conclusions.split(",") if conclusions else None
    languages_list = languages.split(",") if languages else None

    # 1. Fetch Builds (with Language join)
    builds_data = raw_build_run_repo.find_builds_with_filters(
        date_start=date_start,
        date_end=date_end,
        conclusions=conclusions_list,
        ci_provider=ci_provider,
        languages=languages_list,
        skip=skip,
        limit=limit,
    )

    # 2. Fetch Stats
    stats = raw_build_run_repo.get_stats_with_filters(
        date_start=date_start,
        date_end=date_end,
        conclusions=conclusions_list,
        ci_provider=ci_provider,
        languages=languages_list,
    )

    # Serialize builds
    processed_builds = []
    for build in builds_data:
        processed_builds.append(
            {
                "id": str(build.get("_id")),
                "raw_repo_id": str(build.get("raw_repo_id")),
                "repo_name": build.get("repo_name"),
                "branch": build.get("branch"),
                "commit_sha": (
                    build.get("commit_sha", "")[:8] if build.get("commit_sha") else ""
                ),
                "conclusion": build.get("conclusion"),
                "run_started_at": (
                    build["run_started_at"].isoformat()
                    if build.get("run_started_at")
                    else None
                ),
                "duration_seconds": build.get("duration_seconds"),
                "language": build.get("language") or "Unknown",
                "ci_provider": build.get("provider") or "unknown",
            }
        )

    return {
        "builds": processed_builds,
        "stats": stats,
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": stats.get("total_builds", 0),
        },
    }


@router.get("/filter-options")
def get_filter_options(
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get dynamic filter options from raw data.
    Returns distinct languages and CI providers found in the database.
    """
    # CI Provider human-readable labels
    CI_PROVIDER_LABELS = {
        "github_actions": "GitHub Actions",
        "circleci": "CircleCI",
        "travis_ci": "Travis CI",
    }

    raw_build_repo = RawBuildRunRepository(db)
    # simple distinct queries on indexed fields
    providers = raw_build_repo.collection.distinct("provider")

    # We need RawRepository for languages
    raw_repo_collection = db["raw_repositories"]
    languages = raw_repo_collection.distinct("main_lang")

    # Filter out None/Empty and sort
    providers = sorted([p for p in providers if p])
    languages = sorted([l for l in languages if l])

    return {
        "providers": [
            {
                "value": p,
                "label": CI_PROVIDER_LABELS.get(p, p.replace("_", " ").title()),
            }
            for p in providers
        ],
        "languages": [{"value": l, "label": l.title()} for l in languages],
    }


# ============================================================================
# Splitting Groups Discovery (Wizard Step 3 - for LOO/LTO)
# ============================================================================


@router.get("/splitting-groups")
def get_splitting_groups(
    group_by: str = Query(
        ..., description="Group by dimension: repo_language, time_of_day, etc."
    ),
    num_bins: int = Query(
        4, ge=2, le=10, description="Number of bins for numeric features"
    ),
    time_slots: int = Query(
        4, ge=2, le=12, description="Number of time slots for time_of_day"
    ),
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
    languages: Optional[str] = Query(None, description="Comma-separated languages"),
    conclusions: Optional[str] = Query(
        None, description="Comma-separated conclusions (success,failure)"
    ),
    ci_provider: Optional[str] = Query(None, description="CI provider filter"),
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get available groups for splitting strategies.

    Used by LOO/LTO to show selectable test/val groups with counts.
    Returns groups that actually exist in the filtered dataset.
    """
    import pandas as pd

    from app.entities.enums import GroupByDimension
    from app.services.splitting_strategy_service import SplittingStrategyService

    raw_build_run_repo = RawBuildRunRepository(db)

    # Parse comma-separated values
    conclusions_list = conclusions.split(",") if conclusions else None
    languages_list = languages.split(",") if languages else None

    # Get all builds matching filters (no pagination)
    builds_data = raw_build_run_repo.find_builds_with_filters(
        date_start=date_start,
        date_end=date_end,
        conclusions=conclusions_list,
        ci_provider=ci_provider,
        languages=languages_list,
        skip=0,
        limit=100000,  # Get all for grouping
    )

    if not builds_data:
        return {
            "group_by": group_by,
            "groups": [],
            "total_builds": 0,
        }

    # Convert to DataFrame
    df = pd.DataFrame(builds_data)

    # Map column names for compatibility with splitting service
    column_mapping = {
        "language": "repo_language",
    }
    df.rename(columns=column_mapping, inplace=True)

    # Validate group_by
    try:
        group_by_enum = GroupByDimension(group_by)
    except ValueError:
        return {
            "error": f"Invalid group_by: {group_by}",
            "valid_options": [e.value for e in GroupByDimension],
        }

    # Get available groups with dynamic binning
    splitting_service = SplittingStrategyService()
    return splitting_service.get_available_groups(
        df, group_by_enum, num_bins=num_bins, time_slots=time_slots
    )


@router.get("/{scenario_id}/group-preview")
def get_scenario_group_preview(
    scenario_id: str,
    group_by: str = Query(
        ..., description="Group by dimension: repo_language, time_of_day, etc."
    ),
    num_bins: int = Query(
        4, ge=2, le=10, description="Number of bins for numeric features"
    ),
    time_slots: int = Query(
        4, ge=2, le=12, description="Number of time slots for time_of_day"
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get group distribution preview for export configuration.

    This reads from the scenario's master_dataset.parquet if available,
    showing how data would be grouped with the given configuration.
    """
    import pandas as pd

    from app import paths
    from app.entities.enums import GroupByDimension
    from app.services.splitting_strategy_service import SplittingStrategyService

    # Verify scenario access
    service = TrainingScenarioService(db)
    service.get_scenario(scenario_id, str(current_user["_id"]))

    # Try to load master dataset
    scenario_dir = paths.get_training_dataset_dir(scenario_id)
    master_file = scenario_dir / "master_dataset.parquet"

    if not master_file.exists():
        return {
            "error": "Master dataset not yet materialized. Run dataset generation first.",
            "groups": [],
            "total_builds": 0,
        }

    df = pd.read_parquet(master_file)

    # Validate group_by
    try:
        group_by_enum = GroupByDimension(group_by)
    except ValueError:
        return {
            "error": f"Invalid group_by: {group_by}",
            "valid_options": [e.value for e in GroupByDimension],
        }

    # Get group distribution with dynamic binning
    splitting_service = SplittingStrategyService()
    return splitting_service.get_available_groups(
        df, group_by_enum, num_bins=num_bins, time_slots=time_slots
    )


@router.get("/{scenario_id}/splitting-groups")
def get_scenario_splitting_groups(
    scenario_id: str,
    dimension: str = Query(..., description="Grouping dimension"),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get splitting groups for an existing scenario.
    """
    service = TrainingScenarioService(db)
    # Check access
    service.get_scenario(scenario_id, str(current_user["_id"]))

    return service.get_splitting_group_values(scenario_id, dimension)


@router.get("/", response_model=TrainingScenarioListResponse)
def list_scenarios(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> TrainingScenarioListResponse:
    """List training scenarios."""
    service = TrainingScenarioService(db)

    # Validate status enum if provided
    status_enum = None
    if status:
        try:
            status_enum = ScenarioStatus(status)
        except ValueError:
            pass  # Ignore invalid status or handle error

    scenarios, total = service.list_scenarios(
        skip=skip,
        limit=limit,
        status_filter=status_enum,
        q=q,
    )
    return {
        "items": scenarios,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/", response_model=TrainingScenarioResponse)
async def create_training_scenario(
    scenario: TrainingScenarioCreateDTO,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> TrainingScenarioResponse:
    """Create a new training scenario."""
    service = TrainingScenarioService(db)
    return service.create_scenario(str(current_user["_id"]), scenario)


@router.get("/{scenario_id}", response_model=TrainingScenarioResponse)
def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> TrainingScenarioResponse:
    """Get training scenario details."""
    service = TrainingScenarioService(db)
    return service.get_scenario(scenario_id, str(current_user["_id"]))


@router.patch("/{scenario_id}", response_model=TrainingScenarioResponse)
async def update_training_scenario(
    scenario_id: str,
    update_data: TrainingScenarioUpdateDTO,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> TrainingScenarioResponse:
    """Update training scenario."""
    service = TrainingScenarioService(db)
    return service.update_scenario(scenario_id, str(current_user["_id"]), update_data)


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, bool]:
    """Delete training scenario."""
    service = TrainingScenarioService(db)
    service.delete_scenario(scenario_id, str(current_user["_id"]))
    return {"deleted": True}


# ============================================================================
# Pipeline Actions
# ============================================================================


@router.post("/{scenario_id}/ingest")
def start_ingestion(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """Start ingestion phase (Phase 1)."""
    service = TrainingIngestionService(db)
    return service.start_ingestion(scenario_id, str(current_user["_id"]))


@router.post("/{scenario_id}/process")
def start_processing(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """Start processing phase (Phase 2)."""
    service = TrainingProcessingService(db)
    return service.start_processing(scenario_id, str(current_user["_id"]))


@router.post("/{scenario_id}/generate")
def generate_dataset(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """Generate dataset (Phase 3 - Split & Export)."""
    service = TrainingScenarioService(db)
    return service.generate_dataset(
        scenario_id,
        str(current_user["_id"]),
    )


# ============================================================================
# Build Listing
# ============================================================================


@router.get("/{scenario_id}/ingestion-builds")
def get_ingestion_builds(
    scenario_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(
        None,
        description="Filter by status: pending, ingesting, ingested, missing_resource",
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    List ingestion builds for a scenario (Phase 1).

    Shows TrainingIngestionBuild data with resource status breakdown.
    """
    service = TrainingIngestionService(db)
    response = service.get_ingestion_builds(
        scenario_id=scenario_id,
        user_id=str(current_user["_id"]),
        skip=skip,
        limit=limit,
        status_filter=status,
    )
    return response.model_dump()


@router.get("/{scenario_id}/enrichment-builds")
def get_enrichment_builds(
    scenario_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    extraction_status: Optional[str] = Query(
        None,
        description="Filter by status: pending, completed, failed, partial",
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    List enrichment builds for a scenario (Phase 2).

    Shows TrainingEnrichmentBuild data with extraction status and features.
    """
    service = TrainingProcessingService(db)
    response = service.get_enrichment_builds(
        scenario_id=scenario_id,
        user_id=str(current_user["_id"]),
        skip=skip,
        limit=limit,
        extraction_status=extraction_status,
    )
    return response.model_dump()


@router.get("/{scenario_id}/enrichment-builds/{build_id}")
def get_enrichment_build_detail(
    scenario_id: str,
    build_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get detailed view of an enrichment build.
    """
    service = TrainingProcessingService(db)
    return service.get_enrichment_build_detail(
        scenario_id=scenario_id,
        build_id=build_id,
        user_id=str(current_user["_id"]),
    )


@router.get("/{scenario_id}/scan-status")
def get_scan_status(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get scan status summary for a scenario.

    Returns counts of scans completed/pending/failed.
    """
    service = TrainingScenarioService(db)
    return service.get_scan_status(
        scenario_id=scenario_id,
        user_id=str(current_user["_id"]),
    )


# ============================================================================
# Retry Actions
# ============================================================================


@router.post("/{scenario_id}/retry-ingestion")
def retry_ingestion(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """Retry failed ingestion builds."""
    service = TrainingIngestionService(db)
    return service.retry_ingestion(scenario_id, str(current_user["_id"]))


@router.post("/{scenario_id}/retry-processing")
def retry_processing(
    scenario_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """Retry failed processing builds."""
    service = TrainingProcessingService(db)
    return service.retry_processing(scenario_id, str(current_user["_id"]))


# ============================================================================
# Commit Scans
# ============================================================================


@router.get("/{scenario_id}/commit-scans")
def get_commit_scans(
    scenario_id: str,
    tool_type: Optional[str] = Query(
        None, description="Filter by tool: trivy or sonarqube"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    List commit scans for a scenario.

    Returns paginated list of scans for Trivy and/or SonarQube.
    """
    from bson import ObjectId

    from app.repositories.sonar_commit_scan import SonarCommitScanRepository
    from app.repositories.trivy_commit_scan import TrivyCommitScanRepository

    # Verify scenario access
    service = TrainingScenarioService(db)
    service.get_scenario(scenario_id, str(current_user["_id"]))

    scenario_oid = ObjectId(scenario_id)
    result = {}

    # Fetch Trivy scans
    if tool_type is None or tool_type == "trivy":
        trivy_repo = TrivyCommitScanRepository(db)
        trivy_items, trivy_total = trivy_repo.list_by_scenario(
            scenario_oid, skip, limit
        )
        result["trivy"] = {
            "items": [
                {
                    "id": str(scan.id),
                    "commit_sha": scan.commit_sha,
                    "repo_full_name": scan.repo_full_name,
                    "status": (
                        scan.status.value
                        if hasattr(scan.status, "value")
                        else scan.status
                    ),
                    "error_message": scan.error_message,
                    "builds_affected": scan.builds_affected,
                    "retry_count": scan.retry_count,
                    "started_at": (
                        scan.started_at.isoformat() if scan.started_at else None
                    ),
                    "completed_at": (
                        scan.completed_at.isoformat() if scan.completed_at else None
                    ),
                }
                for scan in trivy_items
            ],
            "total": trivy_total,
            "skip": skip,
            "limit": limit,
        }

    # Fetch SonarQube scans
    if tool_type is None or tool_type == "sonarqube":
        sonar_repo = SonarCommitScanRepository(db)
        sonar_items, sonar_total = sonar_repo.list_by_scenario(
            scenario_oid, skip, limit
        )
        result["sonarqube"] = {
            "items": [
                {
                    "id": str(scan.id),
                    "commit_sha": scan.commit_sha,
                    "repo_full_name": scan.repo_full_name,
                    "status": (
                        scan.status.value
                        if hasattr(scan.status, "value")
                        else scan.status
                    ),
                    "error_message": scan.error_message,
                    "builds_affected": scan.builds_affected,
                    "retry_count": scan.retry_count,
                    "started_at": (
                        scan.started_at.isoformat() if scan.started_at else None
                    ),
                    "completed_at": (
                        scan.completed_at.isoformat() if scan.completed_at else None
                    ),
                }
                for scan in sonar_items
            ],
            "total": sonar_total,
            "skip": skip,
            "limit": limit,
        }

    return result


@router.post("/{scenario_id}/commit-scans/{commit_sha}/retry")
def retry_commit_scan(
    scenario_id: str,
    commit_sha: str,
    tool_type: str = Query(..., description="Tool to retry: trivy or sonarqube"),
    current_user: User = Depends(get_current_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
) -> Dict[str, Any]:
    """
    Retry a failed commit scan.
    """
    from bson import ObjectId

    from app.repositories.sonar_commit_scan import SonarCommitScanRepository
    from app.repositories.trivy_commit_scan import TrivyCommitScanRepository

    # Verify scenario access
    service = TrainingScenarioService(db)
    service.get_scenario(scenario_id, str(current_user["_id"]))

    scenario_oid = ObjectId(scenario_id)

    if tool_type == "trivy":
        repo = TrivyCommitScanRepository(db)
        scan = repo.find_by_scenario_and_commit(scenario_oid, commit_sha)
        if not scan:
            return {"success": False, "message": "Scan not found"}
        repo.increment_retry(scan.id)
        # TODO: Dispatch scan task
        return {"success": True, "message": "Trivy scan queued for retry"}

    elif tool_type == "sonarqube":
        repo = SonarCommitScanRepository(db)
        scan = repo.find_by_scenario_and_commit(scenario_oid, commit_sha)
        if not scan:
            return {"success": False, "message": "Scan not found"}
        repo.increment_retry(scan.id)
        # TODO: Dispatch scan task
        return {"success": True, "message": "SonarQube scan queued for retry"}

    return {"success": False, "message": f"Unknown tool type: {tool_type}"}

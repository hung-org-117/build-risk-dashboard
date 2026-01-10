from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.database.mongo import get_db
from app.dtos.training_scenario import (
    TrainingScenarioCreate,
    TrainingScenarioResponse,
    TrainingScenarioUpdate,
)
from app.entities.training_scenario import ScenarioStatus
from app.entities.user import User
from app.middleware.auth import get_current_user
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
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
    exclude_bots: bool = Query(True, description="Exclude bot commits"),
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """
    Preview builds matching filter criteria.

    Used by Training Scenario wizard to preview available builds before creating a scenario.
    Returns paginated builds and aggregate stats.
    """
    raw_repo_repo = RawRepositoryRepository(db)
    raw_build_run_repo = RawBuildRunRepository(db)

    # Parse comma-separated values
    conclusions_list = conclusions.split(",") if conclusions else None
    languages_list = languages.split(",") if languages else None

    # Get repo IDs filtered by language
    repo_ids = None
    if languages_list:
        # Find repos matching the languages
        language_query = {
            "main_lang": {"$in": [lang.lower() for lang in languages_list]}
        }
        matching_repos = list(raw_repo_repo.collection.find(language_query, {"_id": 1}))
        repo_ids = [r["_id"] for r in matching_repos]

        # If no repos match language, return empty result
        if not repo_ids:
            return {
                "builds": [],
                "stats": {
                    "total_builds": 0,
                    "total_repos": 0,
                    "outcome_distribution": {"success": 0, "failure": 0, "other": 0},
                },
                "pagination": {"skip": skip, "limit": limit, "total": 0},
            }

    # Get builds with filters
    builds, stats = raw_build_run_repo.find_with_filters(
        date_start=date_start,
        date_end=date_end,
        conclusions=conclusions_list,
        ci_provider=ci_provider,
        exclude_bots=exclude_bots,
        repo_ids=repo_ids,
        skip=skip,
        limit=limit,
    )

    # Serialize builds
    builds_data = []
    for build in builds:
        builds_data.append(
            {
                "id": str(build.id),
                "raw_repo_id": str(build.raw_repo_id),
                "repo_name": build.repo_name,
                "branch": build.branch,
                "commit_sha": build.commit_sha[:8] if build.commit_sha else "",
                "conclusion": (
                    build.conclusion.value
                    if hasattr(build.conclusion, "value")
                    else build.conclusion
                ),
                "run_started_at": (
                    build.run_started_at.isoformat() if build.run_started_at else None
                ),
                "duration_seconds": build.duration_seconds,
            }
        )

    return {
        "builds": builds_data,
        "stats": stats,
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": stats.get("total_builds", 0),
        },
    }


@router.get("/", response_model=List[TrainingScenarioResponse])
def list_scenarios(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> List[TrainingScenarioResponse]:
    """List training scenarios."""
    service = TrainingScenarioService(db)

    # Validate status enum if provided
    status_enum = None
    if status:
        try:
            status_enum = ScenarioStatus(status)
        except ValueError:
            pass  # Ignore invalid status or handle error

    scenarios, _ = service.list_scenarios(
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        status_filter=status_enum,
        q=q,
    )
    return scenarios


@router.post("/", response_model=TrainingScenarioResponse)
def create_scenario(
    data: TrainingScenarioCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> TrainingScenarioResponse:
    """Create a new training scenario."""
    service = TrainingScenarioService(db)
    return service.create_scenario(str(current_user.id), data)


@router.get("/{scenario_id}", response_model=TrainingScenarioResponse)
def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> TrainingScenarioResponse:
    """Get training scenario details."""
    service = TrainingScenarioService(db)
    return service.get_scenario(scenario_id, str(current_user.id))


@router.put("/{scenario_id}", response_model=TrainingScenarioResponse)
def update_scenario(
    scenario_id: str,
    data: TrainingScenarioUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> TrainingScenarioResponse:
    """Update training scenario."""
    service = TrainingScenarioService(db)
    return service.update_scenario(scenario_id, str(current_user.id), data)


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, bool]:
    """Delete training scenario."""
    service = TrainingScenarioService(db)
    service.delete_scenario(scenario_id, str(current_user.id))
    return {"deleted": True}


# ============================================================================
# Pipeline Actions
# ============================================================================


@router.post("/{scenario_id}/ingest")
def start_ingestion(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Start ingestion phase (Phase 1)."""
    service = TrainingScenarioService(db)
    return service.start_ingestion(scenario_id, str(current_user.id))


@router.post("/{scenario_id}/process")
def start_processing(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Start processing phase (Phase 2)."""
    service = TrainingScenarioService(db)
    return service.start_processing(scenario_id, str(current_user.id))


@router.post("/{scenario_id}/generate")
def generate_dataset(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Generate dataset (Phase 3 - Split & Export)."""
    service = TrainingScenarioService(db)
    return service.generate_dataset(scenario_id, str(current_user.id))


# ============================================================================
# Artifacts
# ============================================================================


@router.get("/{scenario_id}/splits")
def get_scenario_splits(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Get generated split files."""
    service = TrainingScenarioService(db)
    return service.get_scenario_splits(scenario_id, str(current_user.id))

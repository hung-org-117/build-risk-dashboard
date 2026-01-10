"""
ML Scenarios API - Endpoints for ML Dataset Scenario Builder.

Provides:
- CRUD operations for scenarios
- YAML config upload/update
- Split file downloads
- Status queries
"""

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from pymongo.database import Database

from app.database.mongo import get_db
from app.entities.ml_scenario import MLScenarioStatus
from app.middleware.rbac import Permission, RequirePermission
from app.services.ml_scenario_service import MLScenarioService
from app import paths

router = APIRouter(prefix="/ml-scenarios", tags=["ML Scenarios"])


@router.get("")
def list_scenarios(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, description="Filter by status"),
    q: Optional[str] = Query(default=None, description="Search by name"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """List ML scenarios for the current user."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    # Parse status filter
    parsed_status = None
    if status_filter:
        try:
            parsed_status = MLScenarioStatus(status_filter)
        except ValueError:
            pass

    scenarios, total = ml_scenario_service.list_scenarios(
        user_id=user_id,
        skip=skip,
        limit=limit,
        status_filter=parsed_status,
        q=q,
    )

    return {
        "items": scenarios,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_scenario(
    name: str = Form(..., description="Scenario name"),
    yaml_config: str = Form(..., description="YAML configuration"),
    description: Optional[str] = Form(default=None),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.MANAGE_DATASETS)),
):
    """Create a new ML scenario from YAML config."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    return ml_scenario_service.create_scenario(
        user_id=user_id,
        name=name,
        yaml_config=yaml_config,
        description=description,
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_scenario_yaml(
    name: str = Form(..., description="Scenario name"),
    file: UploadFile = File(..., description="YAML config file"),
    description: Optional[str] = Form(default=None),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.MANAGE_DATASETS)),
):
    """Upload a YAML file to create a new ML scenario."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    # Read YAML content
    yaml_content = await file.read()
    yaml_config = yaml_content.decode("utf-8")

    return ml_scenario_service.create_scenario(
        user_id=user_id,
        name=name,
        yaml_config=yaml_config,
        description=description,
    )


@router.get("/{scenario_id}")
def get_scenario(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """Get scenario details."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    return ml_scenario_service.get_scenario(
        scenario_id=scenario_id,
        user_id=user_id,
    )


@router.patch("/{scenario_id}")
def update_scenario(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    name: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    yaml_config: Optional[str] = Form(default=None),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.MANAGE_DATASETS)),
):
    """Update scenario fields."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    return ml_scenario_service.update_scenario(
        scenario_id=scenario_id,
        user_id=user_id,
        name=name,
        description=description,
        yaml_config=yaml_config,
    )


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.MANAGE_DATASETS)),
):
    """Delete a scenario and all associated data."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    ml_scenario_service.delete_scenario(
        scenario_id=scenario_id,
        user_id=user_id,
    )
    return None


@router.get("/{scenario_id}/config")
def get_scenario_config(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """Get the raw YAML config for a scenario."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    scenario = ml_scenario_service.get_scenario(
        scenario_id=scenario_id,
        user_id=user_id,
    )

    # Read from file if exists, otherwise from DB
    config_path = paths.get_ml_scenario_config_path(scenario_id)
    if config_path.exists():
        yaml_content = config_path.read_text()
    else:
        # Fallback to scenario record
        scenario_entity = ml_scenario_service.scenario_repo.find_by_id(scenario_id)
        yaml_content = scenario_entity.yaml_config if scenario_entity else ""

    return {
        "scenario_id": scenario_id,
        "yaml_config": yaml_content,
    }


@router.post("/{scenario_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def start_scenario_generation(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.MANAGE_DATASETS)),
):
    """Start dataset generation for a scenario."""
    from app.tasks.ml_scenario_tasks import start_scenario_generation as start_task

    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    # Verify access and get scenario
    scenario = ml_scenario_service.get_scenario(
        scenario_id=scenario_id,
        user_id=user_id,
    )

    # Check if already processing
    if scenario["status"] in ["filtering", "ingesting", "processing", "splitting"]:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario is already being processed",
        )

    # Dispatch Celery task
    task = start_task.delay(scenario_id)

    return {
        "scenario_id": scenario_id,
        "task_id": task.id,
        "status": "queued",
        "message": "Dataset generation started",
    }


@router.get("/{scenario_id}/splits")
def get_scenario_splits(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """Get all generated split files for a scenario."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    splits = ml_scenario_service.get_scenario_splits(
        scenario_id=scenario_id,
        user_id=user_id,
    )

    return {
        "scenario_id": scenario_id,
        "splits": splits,
    }


@router.get("/{scenario_id}/splits/{split_type}/download")
def download_split_file(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    split_type: str = PathParam(..., description="Split type: train, validation, test"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """Download a specific split file."""
    ml_scenario_service = MLScenarioService(db)
    user_id = str(current_user["_id"])

    # Permission check
    ml_scenario_service.get_scenario(scenario_id, user_id)

    # Find split record
    split = ml_scenario_service.split_repo.find_by_scenario_and_type(
        scenario_id=scenario_id,
        split_type=split_type,
    )

    if not split:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Split '{split_type}' not found for scenario {scenario_id}",
        )

    # Get file path
    file_path = paths.get_ml_dataset_split_path(
        scenario_id=scenario_id,
        split_type=split_type,
        format=split.file_format,
    )

    if not file_path.exists():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Split file not found on disk",
        )

    return FileResponse(
        path=str(file_path),
        filename=f"{split_type}.{split.file_format}",
        media_type="application/octet-stream",
    )


# =============================================================================
# YAML Validation & Documentation Endpoints
# =============================================================================


@router.post("/validate")
def validate_yaml_config(
    yaml_config: str = Form(..., description="YAML configuration to validate"),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Validate YAML configuration without creating a scenario.

    Returns validation result with detailed error messages if invalid.
    """
    from app.services.yaml_validator import YAMLValidatorService

    result = YAMLValidatorService.validate_yaml_string(yaml_config)

    return {
        "valid": result.valid,
        "errors": [
            {
                "field": e.field,
                "message": e.message,
                "expected": e.expected,
                "got": e.got,
            }
            for e in result.errors
        ],
        "warnings": result.warnings,
    }


@router.get("/sample-templates")
def list_sample_templates(
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    List available sample YAML templates.

    Returns list of templates with name, description, and strategy.
    """
    import yaml
    from pathlib import Path

    sample_scenarios_dir = Path(__file__).parent.parent.parent / "sample_scenarios"

    templates = []
    if sample_scenarios_dir.exists():
        for yaml_file in sorted(sample_scenarios_dir.glob("*.yaml")):
            try:
                content = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(content)

                # Extract metadata
                scenario_info = data.get("scenario", {})
                splitting_info = data.get("splitting", {})

                templates.append(
                    {
                        "filename": yaml_file.name,
                        "name": scenario_info.get("name", yaml_file.stem),
                        "description": scenario_info.get(
                            "description", "No description"
                        ),
                        "strategy": splitting_info.get("strategy", "unknown"),
                        "group_by": splitting_info.get("group_by", "language_group"),
                    }
                )
            except Exception:
                # Skip malformed files
                continue

    return {
        "templates": templates,
        "count": len(templates),
    }


@router.get("/sample-templates/{filename}")
def get_sample_template(
    filename: str = PathParam(..., description="Template filename"),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get the content of a sample template by filename.

    Returns the raw YAML content.
    """
    from pathlib import Path
    from fastapi import HTTPException

    sample_scenarios_dir = Path(__file__).parent.parent.parent / "sample_scenarios"
    template_path = sample_scenarios_dir / filename

    # Security: ensure file is within sample_scenarios directory
    try:
        template_path = template_path.resolve()
        if not str(template_path).startswith(str(sample_scenarios_dir.resolve())):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid template filename",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template filename",
        )

    if not template_path.exists() or not template_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{filename}' not found",
        )

    content = template_path.read_text(encoding="utf-8")

    return {
        "filename": filename,
        "content": content,
    }


@router.get("/docs/yaml-schema")
def get_yaml_schema_docs(
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get YAML schema documentation for the frontend.

    Returns structured documentation with all sections, fields, enums,
    and strategy-specific requirements.
    """
    from app.services.yaml_validator import YAMLValidatorService

    return YAMLValidatorService.get_schema_documentation()


@router.get("/{scenario_id}/builds/import")
def list_import_builds(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending, queued, ingesting, ingested, failed",
    ),
    q: Optional[str] = Query(default=None, description="Search by repo name or commit"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    List import builds for a scenario (ingestion phase).

    Returns paginated list of MLScenarioImportBuild records.
    """
    from fastapi import HTTPException

    from app.entities.ml_scenario_import_build import MLScenarioImportBuildStatus
    from app.repositories.ml_scenario import MLScenarioRepository
    from app.repositories.ml_scenario_import_build import (
        MLScenarioImportBuildRepository,
    )

    scenario_repo = MLScenarioRepository(db)
    import_build_repo = MLScenarioImportBuildRepository(db)

    # Verify scenario exists and user has access
    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Parse status filter
    parsed_status = None
    if status_filter:
        try:
            parsed_status = MLScenarioImportBuildStatus(status_filter)
        except ValueError:
            pass

    # Query with filters
    builds, total = import_build_repo.find_by_scenario(
        scenario_id=scenario_id,
        status_filter=parsed_status,
        skip=skip,
        limit=limit,
    )

    # Convert to DTOs
    items = []
    for build in builds:
        items.append(
            {
                "id": str(build.id),
                "scenario_id": str(build.scenario_id),
                "raw_repo_id": str(build.raw_repo_id),
                "raw_build_run_id": str(build.raw_build_run_id),
                "ci_run_id": build.ci_run_id,
                "commit_sha": build.commit_sha,
                "repo_full_name": build.repo_full_name,
                "github_repo_id": build.github_repo_id,
                "status": (
                    build.status.value
                    if hasattr(build.status, "value")
                    else build.status
                ),
                "ingestion_error": build.ingestion_error,
                "resource_status": (
                    {
                        k: {
                            "status": (
                                v.status.value
                                if hasattr(v.status, "value")
                                else v.status
                            ),
                            "error": v.error,
                        }
                        for k, v in (build.resource_status or {}).items()
                    }
                    if build.resource_status
                    else {}
                ),
                "created_at": (
                    build.created_at.isoformat() if build.created_at else None
                ),
                "ingested_at": (
                    build.ingested_at.isoformat() if build.ingested_at else None
                ),
            }
        )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{scenario_id}/builds/enrichment")
def list_enrichment_builds(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by extraction status: pending, in_progress, completed, partial, failed",
    ),
    split_filter: Optional[str] = Query(
        default=None,
        description="Filter by split: train, validation, test",
    ),
    q: Optional[str] = Query(default=None, description="Search by repo name or commit"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    List enrichment builds for a scenario (processing phase).

    Returns paginated list of MLScenarioEnrichmentBuild records.
    """
    from fastapi import HTTPException

    from app.entities.enums import ExtractionStatus
    from app.repositories.ml_scenario import MLScenarioRepository
    from app.repositories.ml_scenario_enrichment_build import (
        MLScenarioEnrichmentBuildRepository,
    )

    scenario_repo = MLScenarioRepository(db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(db)

    # Verify scenario exists
    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Parse status filter
    parsed_status = None
    if status_filter:
        try:
            parsed_status = ExtractionStatus(status_filter)
        except ValueError:
            pass

    # Query with filters
    builds, total = enrichment_build_repo.find_by_scenario(
        scenario_id=scenario_id,
        extraction_status=parsed_status,
        split_assignment=split_filter,
        skip=skip,
        limit=limit,
    )

    # Convert to DTOs
    items = []
    for build in builds:
        items.append(
            {
                "id": str(build.id),
                "scenario_id": str(build.scenario_id),
                "scenario_import_build_id": (
                    str(build.scenario_import_build_id)
                    if build.scenario_import_build_id
                    else None
                ),
                "raw_repo_id": str(build.raw_repo_id),
                "raw_build_run_id": (
                    str(build.raw_build_run_id) if build.raw_build_run_id else None
                ),
                "ci_run_id": build.ci_run_id,
                "commit_sha": build.commit_sha,
                "repo_full_name": build.repo_full_name,
                "outcome": build.outcome,
                "extraction_status": (
                    build.extraction_status.value
                    if hasattr(build.extraction_status, "value")
                    else build.extraction_status
                ),
                "extraction_error": build.extraction_error,
                "feature_vector_id": (
                    str(build.feature_vector_id) if build.feature_vector_id else None
                ),
                "split_assignment": build.split_assignment,
                "created_at": (
                    build.created_at.isoformat() if build.created_at else None
                ),
                "processing_completed_at": (
                    build.processing_completed_at.isoformat()
                    if build.processing_completed_at
                    else None
                ),
            }
        )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{scenario_id}/builds/stats")
def get_builds_stats(
    scenario_id: str = PathParam(..., description="Scenario ID"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(RequirePermission(Permission.VIEW_DATASETS)),
):
    """
    Get aggregated build stats for a scenario.

    Returns counts by status for both import and enrichment builds.
    """
    from app.repositories.ml_scenario_import_build import (
        MLScenarioImportBuildRepository,
    )
    from app.repositories.ml_scenario_enrichment_build import (
        MLScenarioEnrichmentBuildRepository,
    )
    from app.repositories.ml_scenario import MLScenarioRepository
    from fastapi import HTTPException

    scenario_repo = MLScenarioRepository(db)
    import_build_repo = MLScenarioImportBuildRepository(db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    import_stats = import_build_repo.count_by_status(scenario_id)
    enrichment_stats = enrichment_build_repo.count_by_extraction_status(scenario_id)
    split_stats = enrichment_build_repo.count_by_split(scenario_id)

    return {
        "import_builds": import_stats,
        "enrichment_builds": enrichment_stats,
        "split_assignment": split_stats,
    }

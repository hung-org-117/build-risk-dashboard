"""
IngestionBuild Entity - Tracks builds through the ingestion pipeline.

This entity tracks builds through ingestion stages (clone → worktree → logs).
Unified from DatasetImportBuild and MLScenarioImportBuild.

Key design principles:
- Scenario tracking: Links build to TrainingScenario
- Status tracking: Tracks build through PENDING → INGESTING → INGESTED
- Per-resource tracking: Extensible resource_status dict for granular error tracking
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.entities.base import BaseEntity, PyObjectId


class IngestionStatus(str, Enum):
    """Status of a build in the ingestion pipeline."""

    PENDING = "pending"  # Waiting for ingestion
    INGESTING = "ingesting"  # Ingestion in progress
    INGESTED = "ingested"  # Resources ready for processing
    MISSING_RESOURCE = "missing_resource"  # Expected: logs expired (not retryable)
    FAILED = "failed"  # Actual error: timeout, network (retryable)


class ResourceStatus(str, Enum):
    """Status of a single resource in ingestion."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResourceStatusEntry(BaseModel):
    """Status entry for a single resource."""

    status: ResourceStatus = ResourceStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TrainingIngestionBuild(BaseEntity):
    """
    Tracks a build through the ingestion pipeline.

    Links builds to TrainingScenario for ingestion tracking.
    Unified from DatasetImportBuild and MLScenarioImportBuild.
    """

    class Config:
        collection = "training_ingestion_builds"
        use_enum_values = True

    # Parent reference
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to training_scenarios",
    )

    # Raw data references
    raw_repo_id: PyObjectId = Field(
        ...,
        description="Reference to raw_repositories",
    )
    raw_build_run_id: PyObjectId = Field(
        ...,
        description="Reference to raw_build_runs",
    )

    # Pipeline status
    status: IngestionStatus = Field(
        default=IngestionStatus.PENDING,
        description="Pipeline status",
    )

    # Per-resource status tracking
    resource_status: Dict[str, ResourceStatusEntry] = Field(
        default_factory=dict,
        description="Per-resource status. Keys: 'git_history', 'git_worktree', 'build_logs'",
    )

    # Required resources for this build
    required_resources: List[str] = Field(
        default_factory=list,
        description="Resources required based on feature selection",
    )

    # Denormalized fields for quick access
    ci_run_id: str = Field(
        default="",
        description="CI run ID (denormalized from RawBuildRun)",
    )
    commit_sha: str = Field(
        default="",
        description="Commit SHA (denormalized)",
    )
    repo_full_name: str = Field(
        default="",
        description="Repository full name (denormalized)",
    )
    github_repo_id: Optional[int] = Field(
        None,
        description="GitHub repo ID (for path resolution)",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ingestion_started_at: Optional[datetime] = None
    ingested_at: Optional[datetime] = None

    # Error tracking
    ingestion_error: Optional[str] = None

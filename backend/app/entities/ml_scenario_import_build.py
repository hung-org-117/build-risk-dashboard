"""
MLScenarioImportBuild Entity - Tracks builds through ingestion.

Similar to DatasetImportBuild but references MLScenario instead of DatasetVersion.
Tracks per-resource status (clone, worktree, logs).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId
from app.entities.dataset_import_build import ResourceStatus, ResourceStatusEntry


class MLScenarioImportBuildStatus(str, Enum):
    """Status of a build in the ML scenario ingestion pipeline."""

    PENDING = "pending"  # Waiting for ingestion
    INGESTING = "ingesting"  # Ingestion in progress
    INGESTED = "ingested"  # All resources ready
    MISSING_RESOURCE = "missing_resource"  # Expected: logs expired (not retryable)
    FAILED = "failed"  # Actual error (retryable)


class MLScenarioImportBuild(BaseEntity):
    """
    Tracks a build through the ML scenario ingestion pipeline.

    Links builds to MLScenario and tracks resource status.
    """

    class Config:
        collection = "ml_scenario_import_builds"
        use_enum_values = True

    # Parent reference
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to ml_scenarios",
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
    status: MLScenarioImportBuildStatus = Field(
        default=MLScenarioImportBuildStatus.PENDING,
        description="Pipeline status",
    )

    # Per-resource status tracking (reuse from dataset_import_build)
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

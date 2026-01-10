"""
MLScenarioEnrichmentBuild Entity - Tracks builds through processing.

Similar to DatasetEnrichmentBuild but references MLScenario.
Tracks feature extraction status and split assignment.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId
from app.entities.enums import ExtractionStatus


class SplitAssignment(str):
    """Split assignment values."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class MLScenarioEnrichmentBuild(BaseEntity):
    """
    Tracks a build through the ML scenario processing/enrichment pipeline.

    Features are stored in FeatureVector entity, referenced by feature_vector_id.
    Split assignment is set during the splitting phase.
    """

    class Config:
        collection = "ml_scenario_enrichment_builds"
        use_enum_values = True

    # Parent references
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to ml_scenarios",
    )
    scenario_import_build_id: PyObjectId = Field(
        ...,
        description="Reference to ml_scenario_import_builds",
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

    # Feature vector reference (single source of truth)
    feature_vector_id: Optional[PyObjectId] = Field(
        None,
        description="Reference to feature_vectors (stores extracted features)",
    )

    # Extraction status
    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.PENDING,
        description="Feature extraction status",
    )
    extraction_error: Optional[str] = None
    enriched_at: Optional[datetime] = None

    # Split assignment (set during Phase 4: Splitting)
    split_assignment: Optional[str] = Field(
        None,
        description="Split assignment: train | validation | test | null",
    )

    # Group value (for leave-out strategies)
    group_value: Optional[str] = Field(
        None,
        description="Group value for this build (e.g., 'backend', 'morning')",
    )

    # Denormalized for quick queries
    ci_run_id: str = Field(default="")
    commit_sha: str = Field(default="")
    repo_full_name: str = Field(default="")

    # Label (from RawBuildRun.conclusion, used for stratification)
    outcome: Optional[int] = Field(
        None,
        description="Build outcome: 0=success, 1=failure",
    )

    # Timestamps
    build_started_at: Optional[datetime] = Field(
        None,
        description="When the build started (from RawBuildRun.started_at) for temporal ordering",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

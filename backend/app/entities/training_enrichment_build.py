"""
EnrichmentBuild Entity - Tracks builds through processing.

This entity tracks builds through feature extraction.
Unified from DatasetEnrichmentBuild and MLScenarioEnrichmentBuild.

Key design principles:
- References FeatureVector for feature storage (single source of truth)
- Tracks extraction status
- Stores outcome for stratification (computed at export time for each export)
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId
from app.entities.enums import ExtractionStatus


class TrainingEnrichmentBuild(BaseEntity):
    """
    Tracks a build through the processing/enrichment pipeline.

    Features are stored in FeatureVector entity, referenced by feature_vector_id.
    Split assignment is computed at export time (per TrainingDatasetExport).
    """

    class Config:
        collection = "training_enrichment_builds"
        use_enum_values = True

    # Parent references
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to training_scenarios",
    )
    ingestion_build_id: PyObjectId = Field(
        ...,
        description="Reference to ingestion_builds",
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

    # Label (from RawBuildRun.conclusion, used for stratification)
    outcome: Optional[int] = Field(
        None,
        description="Build outcome: 0=success, 1=failure",
    )

    # Denormalized for quick queries
    ci_run_id: str = Field(default="")
    commit_sha: str = Field(default="")
    repo_full_name: str = Field(default="")

    # Timestamps
    build_started_at: Optional[datetime] = Field(
        None,
        description="When the build started (from RawBuildRun) for temporal ordering",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

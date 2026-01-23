"""
TrainingScenario Entity - Training pipeline configuration and tracking.

Stores YAML configuration and tracks scenario progress through phases:
QUEUED → INGESTING → PROCESSING → PROCESSED

This entity replaces both MLScenario and DatasetVersion, providing a unified
training pipeline configuration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.entities.base import BaseEntity, PyObjectId


class ScenarioStatus(str, Enum):
    """Status of training scenario through the pipeline."""

    QUEUED = "queued"  # Initial state after creation
    INGESTING = "ingesting"  # Phase 1: Filter builds, clone, worktree, logs
    INGESTED = "ingested"  # Phase 1 complete, user can review + trigger processing
    PROCESSING = "processing"  # Phase 2: Feature extraction + scans
    PROCESSED = "processed"  # Phase 2 complete. Ready for creating exports.
    FAILED = "failed"  # Error occurred


class DataSourceConfig(BaseModel):
    """Configuration for filtering builds from existing DB data."""

    class Config:
        extra = "allow"

    languages: List[str] = Field(
        default_factory=list,
        description="Languages to include",
    )
    build_source_ids: List[str] = Field(
        default_factory=list,
        description="Filter by builds from specific BuildSource(s)",
    )

    # Build filters
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    conclusions: List[str] = Field(
        default_factory=lambda: ["success", "failure"],
        description="Build conclusions to include",
    )
    ci_provider: str = Field(
        default="all",
        description="CI provider filter: all | github_actions | circleci",
    )


class FeatureConfig(BaseModel):
    """Configuration for feature selection."""

    class Config:
        extra = "allow"

    dag_features: List[str] = Field(
        default_factory=list,
        description="Features from Hamilton DAG (supports wildcards: gh_*, tr_*)",
    )
    scan_metrics: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Scan metrics: {sonarqube: [...], trivy: [...]}",
    )
    # Tool configurations (editable via UI)
    scan_tool_config: Dict[str, Any] = Field(
        default_factory=lambda: {"sonarqube": {}, "trivy": {}},
        description="Scan tool settings: {'sonarqube': {...}, 'trivy': {...}}",
    )
    extractor_configs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-language/framework extractor settings: { global: {...}, repos: {...} }",
    )


class TrainingScenario(BaseEntity):
    """
    Training pipeline configuration and tracking.

    Stores YAML configuration parsed into structured fields,
    and tracks progress through the 4 phases.
    """

    class Config:
        collection = "training_scenarios"
        use_enum_values = True

    # Basic info
    name: str = Field(..., description="Scenario name")
    description: Optional[str] = None
    version: str = Field(default="1.0")

    # Parsed configuration sections
    data_source_config: DataSourceConfig = Field(default_factory=DataSourceConfig)
    feature_config: FeatureConfig = Field(
        default_factory=FeatureConfig
    )  # Includes scan_tool_config and extractor_configs

    # Pipeline status
    status: ScenarioStatus = Field(
        default=ScenarioStatus.QUEUED,
        description="Current pipeline status",
    )
    current_task_id: Optional[str] = Field(
        None,
        description="Celery task ID for current operation",
    )
    error_message: Optional[str] = None

    # Statistics (updated as phases complete)
    builds_total: int = Field(
        default=0,
        description="Total builds matching filter criteria",
    )
    builds_ingested: int = Field(
        default=0,
        description="Builds with ingestion completed",
    )
    builds_missing_resource: int = Field(
        default=0,
        description="Builds with missing resources (not retryable)",
    )
    builds_ingestion_failed: int = Field(
        default=0,
        description="Builds that failed during ingestion (timeout, network). Retryable.",
    )

    builds_features_extracted: int = Field(
        default=0,
        description="Builds with feature extraction completed",
    )
    builds_features_extracted_failed: int = Field(
        default=0,
        description="Builds that failed during feature extraction. Retryable.",
    )

    # Scan tracking
    scans_total: int = Field(
        default=0,
        description="Total scans to run (unique commits × enabled tools)",
    )
    scans_completed: int = Field(
        default=0,
        description="Completed scans",
    )
    scans_failed: int = Field(
        default=0,
        description="Failed scans",
    )

    # Completion flags
    feature_extraction_completed: bool = Field(
        default=False,
        description="All DAG features extracted",
    )
    scan_extraction_completed: bool = Field(
        default=False,
        description="All scans done (completed + failed = total)",
    )
    # User tracking
    created_by: Optional[PyObjectId] = None

    # Phase timestamps
    ingestion_started_at: Optional[datetime] = None
    ingestion_completed_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

"""
TrainingScenario Entity - Training pipeline configuration and tracking.

Stores YAML configuration and tracks scenario progress through phases:
QUEUED → FILTERING → INGESTING → PROCESSING → SPLITTING → COMPLETED

This entity replaces both MLScenario and DatasetVersion, providing a unified
training pipeline configuration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId


class ScenarioStatus(str, Enum):
    """Status of training scenario through the pipeline."""

    QUEUED = "queued"  # Initial state after creation
    FILTERING = "filtering"  # Phase 1: Querying builds from DB
    INGESTING = "ingesting"  # Phase 1: Clone, worktree, logs
    INGESTED = "ingested"  # Phase 1 complete, user can review + trigger processing
    PROCESSING = "processing"  # Phase 2: Feature extraction + scans
    PROCESSED = "processed"  # Phase 2 complete, user can trigger split/download
    SPLITTING = "splitting"  # Phase 3: Applying split strategy
    COMPLETED = "completed"  # All phases done, files ready
    FAILED = "failed"  # Error occurred


class SplitStrategy(str, Enum):
    """Available splitting strategies."""

    STRATIFIED_WITHIN_GROUP = "stratified_within_group"
    LEAVE_ONE_OUT = "leave_one_out"
    LEAVE_TWO_OUT = "leave_two_out"
    IMBALANCED_TRAIN = "imbalanced_train"
    EXTREME_NOVELTY = "extreme_novelty"


class GroupByDimension(str, Enum):
    """Available dimensions for grouping data."""

    LANGUAGE_GROUP = "language_group"
    PERCENTAGE_OF_BUILDS_BEFORE = "percentage_of_builds_before"
    NUMBER_OF_BUILDS_BEFORE = "number_of_builds_before"
    TIME_OF_DAY = "time_of_day"


class DataSourceConfig(BaseEntity):
    """Configuration for filtering builds from existing DB data."""

    class Config:
        extra = "allow"

    # Repository filters
    filter_by: str = Field(
        default="all",
        description="Filter mode: all | by_language | by_name | by_owner",
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Languages to include (if filter_by=by_language)",
    )
    repo_names: List[str] = Field(
        default_factory=list,
        description="Repo full names to include (if filter_by=by_name)",
    )
    owners: List[str] = Field(
        default_factory=list,
        description="Owners/orgs to include (if filter_by=by_owner)",
    )

    # Build filters
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    conclusions: List[str] = Field(
        default_factory=lambda: ["success", "failure"],
        description="Build conclusions to include",
    )
    exclude_bots: bool = True
    ci_provider: str = Field(
        default="all",
        description="CI provider filter: all | github_actions | circleci",
    )


class FeatureConfig(BaseEntity):
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
    exclude: List[str] = Field(
        default_factory=list,
        description="Features to exclude (supports wildcards)",
    )
    # Tool configurations (editable via UI)
    scan_tool_config: Dict[str, Any] = Field(
        default_factory=lambda: {"sonarqube": {}, "trivy": {}},
        description="Scan tool settings: {'sonarqube': {...}, 'trivy': {...}}",
    )
    extractor_configs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-language/framework extractor settings",
    )


class SplittingConfig(BaseEntity):
    """Configuration for data splitting strategy."""

    class Config:
        extra = "allow"

    strategy: SplitStrategy = Field(
        default=SplitStrategy.STRATIFIED_WITHIN_GROUP,
        description="Splitting strategy to apply",
    )
    group_by: GroupByDimension = Field(
        default=GroupByDimension.LANGUAGE_GROUP,
        description="Dimension to group data by",
    )
    groups: List[str] = Field(
        default_factory=list,
        description="Group values (e.g., ['backend', 'fullstack', 'scripting', 'other'])",
    )
    ratios: Dict[str, float] = Field(
        default_factory=lambda: {"train": 0.7, "val": 0.15, "test": 0.15},
        description="Split ratios",
    )
    stratify_by: str = Field(
        default="outcome",
        description="Column to stratify by within groups",
    )

    # Leave-out strategy specific
    test_groups: List[str] = Field(default_factory=list)
    val_groups: List[str] = Field(default_factory=list)
    train_groups: List[str] = Field(default_factory=list)

    # Imbalanced train specific
    reduce_label: Optional[int] = None
    reduce_ratio: float = Field(
        default=0.5,
        description="Ratio to reduce (e.g., 0.5 = reduce 50%)",
    )

    # Extreme novelty specific
    novelty_group: Optional[str] = None
    novelty_label: Optional[int] = None

    # Temporal ordering (default: sort by build time before splitting)
    temporal_ordering: bool = Field(
        default=True,
        description="If true, sort by build_started_at before splitting (train=oldest, test=newest)",
    )


class PreprocessingConfig(BaseEntity):
    """Configuration for data preprocessing."""

    class Config:
        extra = "allow"

    missing_values_strategy: str = Field(
        default="drop_row",
        description="Strategy for missing values: drop_row | fill | skip_feature",
    )
    fill_value: Any = 0
    normalization_method: str = Field(
        default="z_score",
        description="Normalization: z_score | min_max | robust | none",
    )
    strict_mode: bool = Field(
        default=False,
        description="If true, fail if any feature is missing",
    )


class OutputConfig(BaseEntity):
    """Configuration for output files."""

    class Config:
        extra = "allow"

    format: str = Field(
        default="parquet",
        description="Output format: parquet | csv | pickle",
    )
    include_metadata: bool = True


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

    # Raw YAML config (for reference/editing)
    yaml_config: str = Field(
        default="",
        description="Raw YAML configuration string",
    )

    # Parsed configuration sections
    data_source_config: DataSourceConfig = Field(default_factory=DataSourceConfig)
    feature_config: FeatureConfig = Field(
        default_factory=FeatureConfig
    )  # Includes scan_tool_config and extractor_configs
    splitting_config: SplittingConfig = Field(default_factory=SplittingConfig)
    preprocessing_config: PreprocessingConfig = Field(
        default_factory=PreprocessingConfig
    )
    output_config: OutputConfig = Field(default_factory=OutputConfig)

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
    builds_features_extracted: int = Field(
        default=0,
        description="Builds with feature extraction completed",
    )
    builds_missing_resource: int = Field(
        default=0,
        description="Builds with missing resources (not retryable)",
    )
    builds_failed: int = Field(
        default=0,
        description="Builds that failed (retryable)",
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

    # Split statistics
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0

    # User tracking
    created_by: Optional[PyObjectId] = None

    # Phase timestamps
    filtering_started_at: Optional[datetime] = None
    filtering_completed_at: Optional[datetime] = None
    ingestion_started_at: Optional[datetime] = None
    ingestion_completed_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    splitting_started_at: Optional[datetime] = None
    splitting_completed_at: Optional[datetime] = None

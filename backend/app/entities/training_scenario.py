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

from pydantic import Field, model_validator

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

    RANDOM_SPLIT = "random_split"
    TIME_SERIES_SPLIT = "time_series_split"
    STRATIFIED_SPLIT = "stratified_split"
    STRATIFIED_WITHIN_GROUP = "stratified_within_group"
    LEAVE_ONE_OUT = "leave_one_out"
    LEAVE_TWO_OUT = "leave_two_out"
    IMBALANCED_TRAIN = "imbalanced_train"
    EXTREME_NOVELTY = "extreme_novelty"


class GroupByDimension(str, Enum):
    """Available dimensions for grouping data."""

    REPO_FULL_NAME = "repo_full_name"
    REPO_LANGUAGE = "repo_language"
    BUILD_CI_PROVIDER = "build_ci_provider"
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
    ci_provider: str = Field(
        default="all",
        description="CI provider filter: all | github_actions | circleci",
    )

    @model_validator(mode="after")
    def validate_filter_config(self) -> "DataSourceConfig":
        """Validate that filter_by has corresponding values."""
        if self.filter_by == "by_language" and not self.languages:
            raise ValueError(
                "filter_by='by_language' requires languages to be specified"
            )
        if self.filter_by == "by_name" and not self.repo_names:
            raise ValueError("filter_by='by_name' requires repo_names to be specified")
        if self.filter_by == "by_owner" and not self.owners:
            raise ValueError("filter_by='by_owner' requires owners to be specified")
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("date_start must be before date_end")
        return self


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
        default=GroupByDimension.REPO_LANGUAGE,
        description="Dimension to group data by",
    )
    groups: List[str] = Field(
        default_factory=list,
        description="Group values (e.g., ['python', 'java', 'go'])",
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

    @model_validator(mode="after")
    def validate_strategy_config(self) -> "SplittingConfig":
        """Validate that required config fields are set for each strategy."""
        # Strategies that require ratios
        ratio_strategies = {
            SplitStrategy.RANDOM_SPLIT,
            SplitStrategy.TIME_SERIES_SPLIT,
            SplitStrategy.STRATIFIED_SPLIT,
            SplitStrategy.STRATIFIED_WITHIN_GROUP,
            SplitStrategy.IMBALANCED_TRAIN,
        }

        # Validate ratio-based strategies have ratios
        if self.strategy in ratio_strategies:
            if not self.ratios:
                raise ValueError(f"{self.strategy.value} strategy requires ratios")
            total = sum(self.ratios.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(f"Ratios must sum to 1.0, got {total:.2f}")

        # Strategy-specific validations
        if self.strategy == SplitStrategy.LEAVE_ONE_OUT:
            if not self.test_groups:
                raise ValueError(
                    "leave_one_out strategy requires test_groups to be specified"
                )
        elif self.strategy == SplitStrategy.LEAVE_TWO_OUT:
            if not self.test_groups or not self.val_groups:
                raise ValueError(
                    "leave_two_out strategy requires test_groups and val_groups"
                )
        elif self.strategy == SplitStrategy.IMBALANCED_TRAIN:
            if self.reduce_label is None:
                raise ValueError(
                    "imbalanced_train strategy requires reduce_label (0 or 1)"
                )
        elif self.strategy == SplitStrategy.EXTREME_NOVELTY:
            if self.novelty_group is None or self.novelty_label is None:
                raise ValueError(
                    "extreme_novelty strategy requires novelty_group and novelty_label"
                )

        return self


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

"""
TrainingDatasetExport Entity - Tracks dataset exports with their configurations.

This entity stores export configuration (splitting, preprocessing, output) and
tracks export status. Multiple exports can be created from a single processed scenario.

Key design principles:
- 1:N relationship with TrainingScenario (many exports per scenario)
- Stores all export-time configuration (splitting, preprocessing, output)
- Tracks export status and statistics
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.entities.base import BaseEntity, PyObjectId
from app.entities.enums import GroupByDimension, SplitStrategy


class ExportStatus(str, Enum):
    """Status of dataset export."""

    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class PreprocessingConfig(BaseModel):
    """Preprocessing configuration for export."""

    class Config:
        extra = "allow"

    missing_values_strategy: str = Field(
        default="drop_row",
        description="Strategy: drop_row | fill_mean | fill_median | fill_zero",
    )
    normalization: str = Field(
        default="z_score",
        description="Normalization: none | z_score | min_max | robust",
    )


class OutputConfig(BaseModel):
    """Output configuration for export."""

    class Config:
        extra = "allow"

    format: str = Field(
        default="parquet",
        description="File format: parquet | csv",
    )
    include_metadata: bool = Field(
        default=True,
        description="Include repo, commit, build_id columns",
    )


class ExportSplittingConfig(BaseModel):
    """Splitting configuration for export (simplified from TrainingScenario)."""

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
    ratios: Dict[str, float] = Field(
        default_factory=lambda: {"train": 0.7, "val": 0.15, "test": 0.15},
        description="Split ratios",
    )
    stratify_by: str = Field(
        default="outcome",
        description="Column to stratify by within groups",
    )

    # Dynamic binning configuration
    num_bins: int = Field(
        default=4,
        ge=2,
        le=10,
        description="Number of bins for numeric features (percentage/number of builds)",
    )
    time_slots: int = Field(
        default=4,
        ge=2,
        le=12,
        description="Number of time slots for time_of_day grouping (divides 24 hours)",
    )

    # Leave-out strategy specific
    test_groups: List[str] = Field(default_factory=list)
    val_groups: List[str] = Field(default_factory=list)
    train_groups: List[str] = Field(default_factory=list)

    # Imbalanced train specific
    reduce_label: Optional[int] = None
    reduce_ratio: float = Field(default=0.5)
    imbalance_reduction_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Percentage of Label 1 to drop from training set (Imbalanced Train)",
    )

    # Extreme novelty specific
    novelty_group: Optional[str] = None
    novelty_label: Optional[int] = Field(
        default=None,
        description="Label to isolate: 0 (success) or 1 (failure). Based on build_status_num.",
    )


class TrainingDatasetExport(BaseEntity):
    """
    Tracks a dataset export with its configuration.

    Created when user initiates export from Export page.
    Multiple exports can be created from a single processed scenario.
    """

    class Config:
        collection = "training_dataset_exports"
        use_enum_values = True

    # Parent reference
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to training_scenarios",
    )

    # Export identification
    name: str = Field(
        default="",
        description="Export name (e.g., 'Export v1', 'LOO Python Test')",
    )

    # Configurations
    splitting_config: ExportSplittingConfig = Field(
        default_factory=ExportSplittingConfig,
        description="Splitting strategy configuration",
    )
    preprocessing_config: PreprocessingConfig = Field(
        default_factory=PreprocessingConfig,
        description="Preprocessing configuration",
    )
    output_config: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output format configuration",
    )

    # Status
    status: ExportStatus = Field(
        default=ExportStatus.QUEUED,
        description="Export status",
    )
    error_message: Optional[str] = None
    current_task_id: Optional[str] = Field(
        None,
        description="Celery task ID for current operation",
    )

    # Statistics (set after generation)
    train_count: int = Field(default=0)
    val_count: int = Field(default=0)
    test_count: int = Field(default=0)
    feature_count: int = Field(default=0)

    # User tracking
    created_by: Optional[PyObjectId] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    generated_at: Optional[datetime] = None
    generation_duration_seconds: Optional[float] = None

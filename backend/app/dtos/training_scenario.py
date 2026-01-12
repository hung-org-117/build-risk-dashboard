from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.entities.training_scenario import (
    GroupByDimension,
    ScenarioStatus,
    SplitStrategy,
)


class DataSourceConfigDTO(BaseModel):
    filter_by: str = "all"
    languages: List[str] = []
    repo_names: List[str] = []
    owners: List[str] = []
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    conclusions: List[str] = ["success", "failure"]
    ci_provider: str = "all"


class FeatureConfigDTO(BaseModel):
    dag_features: List[str] = []
    scan_metrics: Dict[str, List[str]] = {}
    exclude: List[str] = []
    # Tool configurations (editable via UI)
    scan_tool_config: Dict[str, Any] = {}  # SonarQube/Trivy tool settings
    extractor_configs: Dict[str, Any] = {}  # Per-language/framework extractor settings


class SplittingConfigDTO(BaseModel):
    strategy: SplitStrategy = SplitStrategy.STRATIFIED_WITHIN_GROUP
    group_by: GroupByDimension = GroupByDimension.LANGUAGE
    groups: List[str] = []
    ratios: Dict[str, float] = {"train": 0.7, "val": 0.15, "test": 0.15}
    stratify_by: str = "outcome"
    test_groups: List[str] = []
    val_groups: List[str] = []
    train_groups: List[str] = []
    reduce_label: Optional[int] = None
    reduce_ratio: float = 0.5
    novelty_group: Optional[str] = None
    novelty_label: Optional[int] = None
    temporal_ordering: bool = True

    @model_validator(mode="after")
    def validate_strategy_config(self) -> "SplittingConfigDTO":
        """Validate that required config fields are set for each strategy."""
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


class TrainingScenarioCreateDTO(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    version: str = "1.0"
    yaml_config: Optional[str] = None  # Optional - use if importing from YAML

    # UI-based config (optional - ignored if yaml_config is provided)
    data_source_config: Optional[DataSourceConfigDTO] = None
    feature_config: Optional[FeatureConfigDTO] = None
    splitting_config: Optional[SplittingConfigDTO] = None


class TrainingScenarioUpdateDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml_config: Optional[str] = None


class TrainingScenarioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: str
    status: ScenarioStatus
    error_message: Optional[str] = None

    # Configs (serialized)
    data_source_config: DataSourceConfigDTO
    feature_config: FeatureConfigDTO  # Includes scan_tool_config and extractor_configs
    splitting_config: SplittingConfigDTO
    yaml_config: str

    # Statistics
    builds_total: int = 0
    builds_ingested: int = 0
    builds_features_extracted: int = 0
    builds_missing_resource: int = 0
    builds_failed: int = 0

    # Scan Stats
    scans_total: int = 0
    scans_completed: int = 0
    scans_failed: int = 0

    # Split counts
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0

    # User info
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Phase timestamps
    filtering_completed_at: Optional[datetime] = None
    ingestion_completed_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    splitting_completed_at: Optional[datetime] = None

    # Flags
    feature_extraction_completed: bool = False
    scan_extraction_completed: bool = False


class TrainingScenarioListResponse(BaseModel):
    items: List[TrainingScenarioResponse]
    total: int
    skip: int
    limit: int

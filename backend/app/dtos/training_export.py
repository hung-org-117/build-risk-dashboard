from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.entities.training_dataset_export import (
    ExportSplittingConfig,
    ExportStatus,
    OutputConfig,
    PreprocessingConfig,
    TrainingDatasetExport,
)


class ExportCreateDTO(BaseModel):
    """DTO for creating a new export."""

    name: str = Field(default="", description="Export name")
    splitting_config: ExportSplittingConfig = Field(
        default_factory=ExportSplittingConfig
    )
    preprocessing_config: PreprocessingConfig = Field(
        default_factory=PreprocessingConfig
    )
    output_config: OutputConfig = Field(default_factory=OutputConfig)


class ExportResponse(BaseModel):
    """Response model for export."""

    id: str
    scenario_id: str
    name: str
    splitting_config: Dict[str, Any]
    preprocessing_config: Dict[str, Any]
    output_config: Dict[str, Any]
    status: str
    error_message: Optional[str] = None
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    feature_count: int = 0
    created_at: str
    generated_at: Optional[str] = None
    generation_duration_seconds: Optional[float] = None

    @classmethod
    def from_entity(cls, export: TrainingDatasetExport) -> "ExportResponse":
        return cls(
            id=str(export.id),
            scenario_id=str(export.scenario_id),
            name=export.name,
            splitting_config=export.splitting_config.model_dump(),
            preprocessing_config=export.preprocessing_config.model_dump(),
            output_config=export.output_config.model_dump(),
            status=(
                export.status.value
                if hasattr(export.status, "value")
                else export.status
            ),
            error_message=export.error_message,
            train_count=export.train_count,
            val_count=export.val_count,
            test_count=export.test_count,
            feature_count=export.feature_count,
            created_at=export.created_at.isoformat(),
            generated_at=(
                export.generated_at.isoformat() if export.generated_at else None
            ),
            generation_duration_seconds=export.generation_duration_seconds,
        )


class ExportListResponse(BaseModel):
    """Response model for export list."""

    items: List[ExportResponse]
    total: int
    skip: int
    limit: int


class SplitResponse(BaseModel):
    """Response model for a dataset split."""

    id: str
    export_id: str
    split_type: str
    record_count: int
    feature_count: int
    class_distribution: Dict[str, int]
    group_distribution: Dict[str, int]
    file_path: str
    file_size_bytes: int
    file_format: str
    generated_at: str

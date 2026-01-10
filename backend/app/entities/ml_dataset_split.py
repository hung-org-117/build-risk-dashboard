"""
MLDatasetSplit Entity - Tracks generated split files.

Stores metadata about each split file (train, val, test)
including record counts, class distribution, and file paths.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId


class MLDatasetSplit(BaseEntity):
    """
    Tracks a generated dataset split file.

    Created during Phase 4: Splitting.
    """

    class Config:
        collection = "ml_dataset_splits"

    # Parent reference
    scenario_id: PyObjectId = Field(
        ...,
        description="Reference to ml_scenarios",
    )

    # Split identification
    split_type: str = Field(
        ...,
        description="Split type: train | validation | test | fold_N",
    )

    # Statistics
    record_count: int = Field(
        default=0,
        description="Number of records in this split",
    )
    feature_count: int = Field(
        default=0,
        description="Number of features in this split",
    )
    class_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Label distribution: {0: count, 1: count}",
    )

    # Group distribution (for leave-out strategies)
    group_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Group distribution: {group_name: count}",
    )

    # File metadata
    file_path: str = Field(
        default="",
        description="Relative path to generated file from DATA_DIR",
    )
    file_size_bytes: int = Field(
        default=0,
        description="File size in bytes",
    )
    file_format: str = Field(
        default="parquet",
        description="File format: parquet | csv | pickle",
    )

    # Feature list (for reference/validation)
    feature_names: list = Field(
        default_factory=list,
        description="List of feature column names",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generation_duration_seconds: Optional[float] = None

    # Checksums for data integrity
    checksum_md5: Optional[str] = Field(
        None,
        description="MD5 checksum of the file",
    )

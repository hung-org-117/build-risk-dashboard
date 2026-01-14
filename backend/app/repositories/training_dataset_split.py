"""
Repository for DatasetSplit entity.

Tracks generated dataset split files.
Updated to use export_id as primary reference (supports multi-export).
"""

from datetime import datetime
from typing import Dict, List, Optional

from pymongo.database import Database

from app.entities.training_dataset_split import TrainingDatasetSplit

from .base import BaseRepository


class TrainingDatasetSplitRepository(BaseRepository[TrainingDatasetSplit]):
    """MongoDB repository for dataset splits."""

    def __init__(self, db: Database):
        super().__init__(db, "training_dataset_splits", TrainingDatasetSplit)

    def find_by_export(
        self,
        export_id: str,
    ) -> List[TrainingDatasetSplit]:
        """
        Get all splits for an export.

        Args:
            export_id: Export ID

        Returns:
            List of dataset splits (train, validation, test)
        """
        return self.find_many(
            {"export_id": self._to_object_id(export_id)},
            sort=[("split_type", 1)],
        )

    def find_by_scenario(
        self,
        scenario_id: str,
    ) -> List[TrainingDatasetSplit]:
        """
        Get all splits for a scenario (across all exports).

        Args:
            scenario_id: Scenario ID

        Returns:
            List of dataset splits
        """
        return self.find_many(
            {"scenario_id": self._to_object_id(scenario_id)},
            sort=[("generated_at", -1), ("split_type", 1)],
        )

    def find_by_export_and_type(
        self,
        export_id: str,
        split_type: str,
    ) -> Optional[TrainingDatasetSplit]:
        """
        Get a specific split by type.

        Args:
            export_id: Export ID
            split_type: Split type (train/validation/test/fold_N)

        Returns:
            DatasetSplit if found
        """
        return self.find_one(
            {
                "export_id": self._to_object_id(export_id),
                "split_type": split_type,
            }
        )

    def create_split(
        self,
        export_id: str,
        scenario_id: str,
        split_type: str,
        record_count: int,
        feature_count: int,
        class_distribution: Dict[str, int],
        group_distribution: Dict[str, int],
        file_path: str,
        file_size_bytes: int,
        file_format: str,
        feature_names: List[str],
        generation_duration_seconds: float,
        checksum_md5: Optional[str] = None,
        fold_id: Optional[str] = None,
    ) -> TrainingDatasetSplit:
        """
        Create a new dataset split record.

        Args:
            export_id: Parent export ID
            scenario_id: Parent scenario ID (denormalized)
            split_type: train/validation/test
            record_count: Number of records in split
            feature_count: Number of features
            class_distribution: Label distribution
            group_distribution: Group distribution
            file_path: Relative path to file
            file_size_bytes: File size
            file_format: parquet/csv
            feature_names: List of feature column names
            generation_duration_seconds: Time to generate
            checksum_md5: Optional MD5 checksum
            fold_id: Optional fold identifier for CV strategies

        Returns:
            Created DatasetSplit
        """
        split = TrainingDatasetSplit(
            export_id=self._to_object_id(export_id),
            scenario_id=self._to_object_id(scenario_id),
            split_type=split_type,
            fold_id=fold_id,
            record_count=record_count,
            feature_count=feature_count,
            class_distribution=class_distribution,
            group_distribution=group_distribution,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            file_format=file_format,
            feature_names=feature_names,
            generation_duration_seconds=generation_duration_seconds,
            checksum_md5=checksum_md5,
            generated_at=datetime.utcnow(),
        )
        return self.insert_one(split)

    def get_total_records(self, export_id: str) -> int:
        """Get total records across all splits for an export."""
        pipeline = [
            {"$match": {"export_id": self._to_object_id(export_id)}},
            {"$group": {"_id": None, "total": {"$sum": "$record_count"}}},
        ]
        results = self.aggregate(pipeline)
        return results[0]["total"] if results else 0

    def get_total_size_bytes(self, export_id: str) -> int:
        """Get total file size across all splits for an export."""
        pipeline = [
            {"$match": {"export_id": self._to_object_id(export_id)}},
            {"$group": {"_id": None, "total": {"$sum": "$file_size_bytes"}}},
        ]
        results = self.aggregate(pipeline)
        return results[0]["total"] if results else 0

    def delete_by_export(self, export_id: str) -> int:
        """Delete all splits for an export."""
        return self.delete_many({"export_id": self._to_object_id(export_id)})

    def delete_by_scenario(self, scenario_id: str, session=None) -> int:
        """Delete all splits for a scenario (across all exports)."""
        return self.delete_many(
            {"scenario_id": self._to_object_id(scenario_id)}, session=session
        )

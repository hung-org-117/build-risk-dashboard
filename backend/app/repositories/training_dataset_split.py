"""
Repository for DatasetSplit entity.

Tracks generated dataset split files.
Renamed from MLDatasetSplitRepository.
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

    def find_by_scenario(
        self,
        scenario_id: str,
    ) -> List[TrainingDatasetSplit]:
        """
        Get all splits for a scenario.

        Args:
            scenario_id: Scenario ID

        Returns:
            List of dataset splits (train, validation, test)
        """
        return self.find_many(
            {"scenario_id": self._to_object_id(scenario_id)},
            sort=[("split_type", 1)],
        )

    def find_by_scenario_and_type(
        self,
        scenario_id: str,
        split_type: str,
    ) -> Optional[TrainingDatasetSplit]:
        """
        Get a specific split by type.

        Args:
            scenario_id: Scenario ID
            split_type: Split type (train/validation/test/fold_N)

        Returns:
            DatasetSplit if found
        """
        return self.find_one(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "split_type": split_type,
            }
        )

    def create_split(
        self,
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
    ) -> TrainingDatasetSplit:
        """
        Create a new dataset split record.

        Args:
            scenario_id: Parent scenario ID
            split_type: train/validation/test/fold_N
            record_count: Number of records in split
            feature_count: Number of features
            class_distribution: Label distribution
            group_distribution: Group distribution
            file_path: Relative path to file
            file_size_bytes: File size
            file_format: parquet/csv/pickle
            feature_names: List of feature column names
            generation_duration_seconds: Time to generate
            checksum_md5: Optional MD5 checksum

        Returns:
            Created DatasetSplit
        """
        split = TrainingDatasetSplit(
            scenario_id=self._to_object_id(scenario_id),
            split_type=split_type,
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

    def get_total_records(self, scenario_id: str) -> int:
        """Get total records across all splits for a scenario."""
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {"$group": {"_id": None, "total": {"$sum": "$record_count"}}},
        ]
        results = self.aggregate(pipeline)
        return results[0]["total"] if results else 0

    def get_total_size_bytes(self, scenario_id: str) -> int:
        """Get total file size across all splits."""
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {"$group": {"_id": None, "total": {"$sum": "$file_size_bytes"}}},
        ]
        results = self.aggregate(pipeline)
        return results[0]["total"] if results else 0

    def delete_by_scenario(self, scenario_id: str) -> int:
        """Delete all splits for a scenario."""
        return self.delete_many({"scenario_id": self._to_object_id(scenario_id)})

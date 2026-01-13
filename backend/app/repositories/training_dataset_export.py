"""
Repository for TrainingDatasetExport entity.

Handles CRUD operations for dataset exports.
Supports multiple exports per scenario with different configurations.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from bson import ObjectId
from pymongo.database import Database

from app.entities.training_dataset_export import (
    ExportSplittingConfig,
    ExportStatus,
    OutputConfig,
    PreprocessingConfig,
    TrainingDatasetExport,
)

from .base import BaseRepository


class TrainingDatasetExportRepository(BaseRepository[TrainingDatasetExport]):
    """MongoDB repository for dataset exports."""

    def __init__(self, db: Database):
        super().__init__(db, "training_dataset_exports", TrainingDatasetExport)

    def find_by_scenario(
        self,
        scenario_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[TrainingDatasetExport], int]:
        """
        Get all exports for a scenario with pagination.

        Args:
            scenario_id: Scenario ID
            skip: Pagination offset
            limit: Max results

        Returns:
            Tuple of (exports list, total count)
        """
        query = {"scenario_id": self._to_object_id(scenario_id)}
        exports = self.find_many(
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )
        total = self.count(query)
        return exports, total

    def find_latest_by_scenario(
        self,
        scenario_id: str,
    ) -> Optional[TrainingDatasetExport]:
        """
        Get the most recent export for a scenario.

        Args:
            scenario_id: Scenario ID

        Returns:
            Latest export or None
        """
        exports = self.find_many(
            {"scenario_id": self._to_object_id(scenario_id)},
            sort=[("created_at", -1)],
            limit=1,
        )
        return exports[0] if exports else None

    def create_export(
        self,
        scenario_id: str,
        name: str,
        splitting_config: ExportSplittingConfig,
        preprocessing_config: PreprocessingConfig,
        output_config: OutputConfig,
        created_by: Optional[str] = None,
    ) -> TrainingDatasetExport:
        """
        Create a new export for a scenario.

        Args:
            scenario_id: Parent scenario ID
            name: Export name
            splitting_config: Splitting configuration
            preprocessing_config: Preprocessing configuration
            output_config: Output configuration
            created_by: User ID

        Returns:
            Created export
        """
        export = TrainingDatasetExport(
            scenario_id=self._to_object_id(scenario_id),
            name=name,
            splitting_config=splitting_config,
            preprocessing_config=preprocessing_config,
            output_config=output_config,
            status=ExportStatus.QUEUED,
            created_by=self._to_object_id(created_by) if created_by else None,
            created_at=datetime.utcnow(),
        )
        return self.insert_one(export)

    def update_status(
        self,
        export_id: str,
        status: ExportStatus,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[TrainingDatasetExport]:
        """Update export status."""
        updates = {"status": status.value}
        if error_message is not None:
            updates["error_message"] = error_message
        if task_id is not None:
            updates["current_task_id"] = task_id
        return self.update_one(self._to_object_id(export_id), updates)

    def mark_completed(
        self,
        export_id: str,
        train_count: int,
        val_count: int,
        test_count: int,
        feature_count: int,
        generation_duration_seconds: float,
    ) -> Optional[TrainingDatasetExport]:
        """Mark export as completed with statistics."""
        return self.update_one(
            self._to_object_id(export_id),
            {
                "status": ExportStatus.COMPLETED.value,
                "train_count": train_count,
                "val_count": val_count,
                "test_count": test_count,
                "feature_count": feature_count,
                "generated_at": datetime.utcnow(),
                "generation_duration_seconds": generation_duration_seconds,
                "error_message": None,
                "current_task_id": None,
            },
        )

    def mark_failed(
        self,
        export_id: str,
        error_message: str,
    ) -> Optional[TrainingDatasetExport]:
        """Mark export as failed."""
        return self.update_one(
            self._to_object_id(export_id),
            {
                "status": ExportStatus.FAILED.value,
                "error_message": error_message,
                "current_task_id": None,
            },
        )

    def delete_by_scenario(self, scenario_id: str) -> int:
        """Delete all exports for a scenario."""
        return self.delete_many({"scenario_id": self._to_object_id(scenario_id)})

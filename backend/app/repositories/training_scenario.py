"""
Repository for TrainingScenario entity.

Provides CRUD and query operations for Training Scenario configurations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from app.entities.training_scenario import TrainingScenario, ScenarioStatus

from .base import BaseRepository


class TrainingScenarioRepository(BaseRepository[TrainingScenario]):
    """MongoDB repository for Training Scenario configurations."""

    def __init__(self, db: Database):
        super().__init__(db, "training_scenarios", TrainingScenario)

    def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 0,
        status_filter: Optional[ScenarioStatus] = None,
        q: Optional[str] = None,
    ) -> tuple[list[TrainingScenario], int]:
        """
        List scenarios for a user with optional filters.

        Args:
            user_id: User ID to filter by
            skip: Pagination offset
            limit: Max results to return
            status_filter: Filter by scenario status
            q: Search query for name/description

        Returns:
            Tuple of (scenarios, total_count)
        """
        query: Dict[str, Any] = {}

        if user_id:
            query["created_by"] = self._to_object_id(user_id)

        if status_filter:
            query["status"] = status_filter.value

        if q:
            query["$or"] = [
                {"name": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
            ]

        return self.paginate(
            query,
            sort=[("updated_at", -1), ("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def list_all(
        self,
        skip: int = 0,
        limit: int = 0,
        status_filter: Optional[ScenarioStatus] = None,
    ) -> tuple[list[TrainingScenario], int]:
        """List all scenarios (admin view)."""
        query: Dict[str, Any] = {}

        if status_filter:
            query["status"] = status_filter.value

        return self.paginate(
            query,
            sort=[("updated_at", -1), ("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def find_by_name(
        self, name: str, user_id: Optional[str] = None
    ) -> Optional[TrainingScenario]:
        """Find scenario by name, optionally scoped to a user."""
        query: Dict[str, Any] = {"name": name}
        if user_id:
            query["created_by"] = self._to_object_id(user_id)
        return self.find_one(query)

    def get_active_scenarios(self) -> List[TrainingScenario]:
        """Get scenarios currently being processed (not completed/failed)."""
        active_statuses = [
            ScenarioStatus.QUEUED.value,
            ScenarioStatus.FILTERING.value,
            ScenarioStatus.INGESTING.value,
            ScenarioStatus.PROCESSING.value,
            ScenarioStatus.SPLITTING.value,
        ]
        return self.find_many(
            {"status": {"$in": active_statuses}},
            sort=[("created_at", 1)],
        )

    def update_status(
        self,
        scenario_id: str,
        status: ScenarioStatus,
        error_message: Optional[str] = None,
    ) -> Optional[TrainingScenario]:
        """Update scenario status with optional error message."""
        updates: Dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow(),
        }

        if error_message is not None:
            updates["error_message"] = error_message
        elif status != ScenarioStatus.FAILED:
            updates["error_message"] = None

        return self.update_one(scenario_id, updates)

    def update_statistics(
        self,
        scenario_id: str,
        builds_total: Optional[int] = None,
        builds_ingested: Optional[int] = None,
        builds_features_extracted: Optional[int] = None,
        builds_missing_resource: Optional[int] = None,
        builds_failed: Optional[int] = None,
    ) -> Optional[TrainingScenario]:
        """Update scenario statistics counters."""
        updates: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if builds_total is not None:
            updates["builds_total"] = builds_total
        if builds_ingested is not None:
            updates["builds_ingested"] = builds_ingested
        if builds_features_extracted is not None:
            updates["builds_features_extracted"] = builds_features_extracted
        if builds_missing_resource is not None:
            updates["builds_missing_resource"] = builds_missing_resource
        if builds_failed is not None:
            updates["builds_failed"] = builds_failed

        return self.update_one(scenario_id, updates)

    def update_split_counts(
        self,
        scenario_id: str,
        train_count: int,
        val_count: int,
        test_count: int,
    ) -> Optional[TrainingScenario]:
        """Update scenario with final split counts after splitting phase."""
        updates = {
            "train_count": train_count,
            "val_count": val_count,
            "test_count": test_count,
            "updated_at": datetime.utcnow(),
        }
        return self.update_one(scenario_id, updates)

    def increment_counter(
        self,
        scenario_id: str,
        counter_field: str,
        increment_by: int = 1,
    ) -> bool:
        """Atomically increment a counter field."""
        result = self.collection.update_one(
            {"_id": self._to_object_id(scenario_id)},
            {
                "$inc": {counter_field: increment_by},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
        return result.modified_count > 0

    def increment_scans_completed(self, scenario_id: str, count: int = 1) -> bool:
        """Increment scans_completed counter atomically."""
        return self.increment_counter(scenario_id, "scans_completed", count)

    def increment_scans_failed(self, scenario_id: str, count: int = 1) -> bool:
        """Increment scans_failed counter atomically."""
        return self.increment_counter(scenario_id, "scans_failed", count)

    def mark_feature_extraction_completed(self, scenario_id: str) -> bool:
        """Mark feature extraction as completed."""
        result = self.collection.update_one(
            {"_id": self._to_object_id(scenario_id)},
            {
                "$set": {
                    "feature_extraction_completed": True,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    def mark_scan_extraction_completed(self, scenario_id: str) -> bool:
        """Mark scan extraction as completed (all scans done)."""
        result = self.collection.update_one(
            {"_id": self._to_object_id(scenario_id)},
            {
                "$set": {
                    "scan_extraction_completed": True,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    def set_scans_total(
        self, scenario_id: str, scans_total: int
    ) -> Optional[TrainingScenario]:
        """Set the total number of scans to run."""
        return self.update_one(
            scenario_id,
            {
                "scans_total": scans_total,
                "scans_completed": 0,
                "scans_failed": 0,
                "scan_extraction_completed": False,
                "updated_at": datetime.utcnow(),
            },
        )

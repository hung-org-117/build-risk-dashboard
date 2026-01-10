"""
Repository for MLScenario entity.

Provides CRUD and query operations for ML Scenario configurations.
"""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.ml_scenario import MLScenario, MLScenarioStatus

from .base import BaseRepository


class MLScenarioRepository(BaseRepository[MLScenario]):
    """MongoDB repository for ML Scenario configurations."""

    def __init__(self, db: Database):
        super().__init__(db, "ml_scenarios", MLScenario)

    def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 0,
        status_filter: Optional[MLScenarioStatus] = None,
        q: Optional[str] = None,
    ) -> tuple[list[MLScenario], int]:
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
        status_filter: Optional[MLScenarioStatus] = None,
    ) -> tuple[list[MLScenario], int]:
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
    ) -> Optional[MLScenario]:
        """
        Find scenario by name, optionally scoped to a user.

        Args:
            name: Scenario name to search for
            user_id: Optional user ID to scope the search

        Returns:
            MLScenario if found, None otherwise
        """
        query: Dict[str, Any] = {"name": name}
        if user_id:
            query["created_by"] = self._to_object_id(user_id)
        return self.find_one(query)

    def get_active_scenarios(self) -> List[MLScenario]:
        """Get scenarios currently being processed (not completed/failed)."""
        active_statuses = [
            MLScenarioStatus.QUEUED.value,
            MLScenarioStatus.FILTERING.value,
            MLScenarioStatus.INGESTING.value,
            MLScenarioStatus.PROCESSING.value,
            MLScenarioStatus.SPLITTING.value,
        ]
        return self.find_many(
            {"status": {"$in": active_statuses}},
            sort=[("created_at", 1)],
        )

    def update_status(
        self,
        scenario_id: str,
        status: MLScenarioStatus,
        error_message: Optional[str] = None,
    ) -> Optional[MLScenario]:
        """
        Update scenario status with optional error message.

        Args:
            scenario_id: Scenario ID to update
            status: New status value
            error_message: Optional error message (for failed status)

        Returns:
            Updated MLScenario or None if not found
        """
        from datetime import datetime

        updates: Dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow(),
        }

        if error_message is not None:
            updates["error_message"] = error_message
        elif status != MLScenarioStatus.FAILED:
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
    ) -> Optional[MLScenario]:
        """
        Update scenario statistics counters.

        Args:
            scenario_id: Scenario ID to update
            builds_total: Total builds found during filtering
            builds_ingested: Builds with completed ingestion
            builds_features_extracted: Builds with completed processing
            builds_missing_resource: Builds with missing resources
            builds_failed: Builds that failed

        Returns:
            Updated MLScenario or None if not found
        """
        from datetime import datetime

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
    ) -> Optional[MLScenario]:
        """
        Update scenario with final split counts after splitting phase.

        Args:
            scenario_id: Scenario ID to update
            train_count: Number of records in train split
            val_count: Number of records in validation split
            test_count: Number of records in test split

        Returns:
            Updated MLScenario or None if not found
        """
        from datetime import datetime

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
        """
        Atomically increment a counter field.

        Args:
            scenario_id: Scenario ID to update
            counter_field: Field name (e.g., "builds_ingested")
            increment_by: Amount to increment (default 1)

        Returns:
            True if document was updated
        """
        from datetime import datetime

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
        from datetime import datetime

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
        from datetime import datetime

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
    ) -> Optional[MLScenario]:
        """Set the total number of scans to run."""
        from datetime import datetime

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

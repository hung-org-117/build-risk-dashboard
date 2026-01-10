"""
Repository for MLScenarioImportBuild entity.

Tracks builds through the ML scenario ingestion pipeline.
Reuses patterns from DatasetImportBuildRepository.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.ml_scenario_import_build import (
    MLScenarioImportBuild,
    MLScenarioImportBuildStatus,
)
from app.entities.dataset_import_build import ResourceStatus, ResourceStatusEntry

from .base import BaseRepository


class MLScenarioImportBuildRepository(BaseRepository[MLScenarioImportBuild]):
    """MongoDB repository for ML scenario import builds."""

    def __init__(self, db: Database):
        super().__init__(db, "ml_scenario_import_builds", MLScenarioImportBuild)

    def find_by_scenario(
        self,
        scenario_id: str,
        status_filter: Optional[MLScenarioImportBuildStatus] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> tuple[list[MLScenarioImportBuild], int]:
        """
        Find all import builds for a scenario.

        Args:
            scenario_id: Scenario ID to filter by
            status_filter: Optional status filter
            skip: Pagination offset
            limit: Max results

        Returns:
            Tuple of (import_builds, total_count)
        """
        query: Dict[str, Any] = {
            "scenario_id": self._to_object_id(scenario_id),
        }
        if status_filter:
            query["status"] = status_filter.value

        return self.paginate(
            query,
            sort=[("created_at", 1)],
            skip=skip,
            limit=limit,
        )

    def find_pending_for_ingestion(
        self,
        scenario_id: str,
        batch_size: int = 50,
    ) -> List[MLScenarioImportBuild]:
        """
        Get builds ready for ingestion (status=PENDING).

        Args:
            scenario_id: Scenario ID
            batch_size: Max builds to return

        Returns:
            List of pending import builds
        """
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "status": MLScenarioImportBuildStatus.PENDING.value,
            },
            sort=[("created_at", 1)],
            limit=batch_size,
        )

    def bulk_create_from_raw_builds(
        self,
        scenario_id: str,
        raw_build_data: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk create import builds from raw build run data.

        Args:
            scenario_id: Scenario ID
            raw_build_data: List of dicts with raw_repo_id, raw_build_run_id,
                           ci_run_id, commit_sha, repo_full_name, github_repo_id

        Returns:
            Number of builds created
        """
        if not raw_build_data:
            return 0

        scenario_oid = self._to_object_id(scenario_id)
        documents = []

        for build_data in raw_build_data:
            doc = MLScenarioImportBuild(
                scenario_id=scenario_oid,
                raw_repo_id=build_data["raw_repo_id"],
                raw_build_run_id=build_data["raw_build_run_id"],
                ci_run_id=build_data.get("ci_run_id", ""),
                commit_sha=build_data.get("commit_sha", ""),
                repo_full_name=build_data.get("repo_full_name", ""),
                github_repo_id=build_data.get("github_repo_id"),
                status=MLScenarioImportBuildStatus.PENDING,
                resource_status={},
                required_resources=build_data.get("required_resources", []),
            )
            documents.append(doc)

        inserted = self.insert_many(documents)
        return len(inserted)

    def update_status(
        self,
        import_build_id: str,
        status: MLScenarioImportBuildStatus,
        error_message: Optional[str] = None,
    ) -> Optional[MLScenarioImportBuild]:
        """Update import build status."""
        updates: Dict[str, Any] = {"status": status.value}

        if status == MLScenarioImportBuildStatus.INGESTING:
            updates["ingestion_started_at"] = datetime.utcnow()
        elif status == MLScenarioImportBuildStatus.INGESTED:
            updates["ingested_at"] = datetime.utcnow()

        if error_message is not None:
            updates["ingestion_error"] = error_message

        return self.update_one(import_build_id, updates)

    def update_resource_status(
        self,
        import_build_id: str,
        resource_name: str,
        resource_status: ResourceStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update status for a specific resource.

        Args:
            import_build_id: Import build ID
            resource_name: Resource name (e.g., "git_history", "git_worktree", "build_logs")
            resource_status: New status for the resource
            error_message: Optional error message

        Returns:
            True if update succeeded
        """
        now = datetime.utcnow()

        update_fields = {
            f"resource_status.{resource_name}.status": resource_status.value,
        }

        if resource_status == ResourceStatus.IN_PROGRESS:
            update_fields[f"resource_status.{resource_name}.started_at"] = now
        elif resource_status in (ResourceStatus.COMPLETED, ResourceStatus.FAILED):
            update_fields[f"resource_status.{resource_name}.completed_at"] = now

        if error_message:
            update_fields[f"resource_status.{resource_name}.error"] = error_message

        result = self.collection.update_one(
            {"_id": self._to_object_id(import_build_id)},
            {"$set": update_fields},
        )
        return result.modified_count > 0

    def count_by_status(self, scenario_id: str) -> Dict[str, int]:
        """
        Get count of builds by status for a scenario.

        Args:
            scenario_id: Scenario ID

        Returns:
            Dict mapping status -> count
        """
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        results = self.aggregate(pipeline)
        return {r["_id"]: r["count"] for r in results}

    def delete_by_scenario(self, scenario_id: str) -> int:
        """Delete all import builds for a scenario."""
        return self.delete_many({"scenario_id": self._to_object_id(scenario_id)})

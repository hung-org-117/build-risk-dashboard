"""
Repository for IngestionBuild entity.

Tracks builds through the training pipeline ingestion phase.
Unified from DatasetImportBuildRepository and MLScenarioImportBuildRepository.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from app.entities.training_ingestion_build import (
    IngestionStatus,
    ResourceStatus,
    TrainingIngestionBuild,
)

from .base import BaseRepository


class TrainingIngestionBuildRepository(BaseRepository[TrainingIngestionBuild]):
    """MongoDB repository for ingestion builds."""

    def __init__(self, db: Database):
        super().__init__(db, "training_ingestion_builds", TrainingIngestionBuild)

    def find_by_scenario(
        self,
        scenario_id: str,
        status_filter: Optional[IngestionStatus] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> tuple[list[TrainingIngestionBuild], int]:
        """
        Find all ingestion builds for a scenario.

        Args:
            scenario_id: Scenario ID to filter by
            status_filter: Optional status filter
            skip: Pagination offset
            limit: Max results

        Returns:
            Tuple of (ingestion_builds, total_count)
        """
        query: Dict[str, Any] = {
            "scenario_id": self._to_object_id(scenario_id),
        }
        if status_filter:
            query["status"] = status_filter.value

        return self.paginate(
            query,
            sort=[("created_at", 1), ("_id", 1)],
            skip=skip,
            limit=limit,
        )

    def find_pending_for_ingestion(
        self,
        scenario_id: str,
        batch_size: int = 50,
    ) -> List[TrainingIngestionBuild]:
        """
        Get builds ready for ingestion (status=PENDING).

        Args:
            scenario_id: Scenario ID
            batch_size: Max builds to return

        Returns:
            List of pending ingestion builds
        """
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "status": IngestionStatus.PENDING.value,
            },
            sort=[("created_at", 1), ("_id", 1)],
            limit=batch_size,
        )

    def find_for_enrichment_with_raw_data(
        self,
        scenario_id: str,
        statuses: List[IngestionStatus],
    ) -> List[Dict[str, Any]]:
        """
        Optimized aggregation for enrichment dispatch.

        Joins with raw_build_runs to get run_created_at and conclusion,
        sorts by run_created_at + _id in the database (not Python).

        This eliminates:
        - 2 separate queries for different statuses
        - N+1 query pattern for raw_build_runs lookup
        - Python-side sorting

        Args:
            scenario_id: Scenario ID
            statuses: List of statuses to include (e.g., [INGESTED, MISSING_RESOURCE])

        Returns:
            List of dicts with ingestion build data + joined raw_build_run fields:
            - _id, scenario_id, raw_repo_id, raw_build_run_id, status
            - ci_run_id, commit_sha, repo_full_name, github_repo_id, created_at
            - run_created_at (from raw_build_runs)
            - run_started_at (from raw_build_runs)
            - conclusion (from raw_build_runs)
        """
        status_values = [s.value for s in statuses]

        pipeline = [
            # Stage 1: Match by scenario and status
            {
                "$match": {
                    "scenario_id": self._to_object_id(scenario_id),
                    "status": {"$in": status_values},
                }
            },
            # Stage 2: Lookup raw_build_runs to get run_created_at and conclusion
            {
                "$lookup": {
                    "from": "raw_build_runs",
                    "localField": "raw_build_run_id",
                    "foreignField": "_id",
                    "as": "raw_run",
                }
            },
            # Stage 3: Unwind the joined array (1:1 relationship expected)
            {"$unwind": {"path": "$raw_run", "preserveNullAndEmptyArrays": True}},
            # Stage 4: Add fields from raw_build_run for sorting and outcome
            {
                "$addFields": {
                    "run_created_at": "$raw_run.run_created_at",
                    "run_started_at": "$raw_run.run_started_at",
                    "conclusion": "$raw_run.conclusion",
                }
            },
            # Stage 5: Sort by run_created_at (oldest first) + _id for determinism
            {"$sort": {"run_created_at": 1, "_id": 1}},
            # Stage 6: Project only needed fields (drop raw_run subdocument)
            {
                "$project": {
                    "_id": 1,
                    "scenario_id": 1,
                    "raw_repo_id": 1,
                    "raw_build_run_id": 1,
                    "status": 1,
                    "ci_run_id": 1,
                    "commit_sha": 1,
                    "repo_full_name": 1,
                    "github_repo_id": 1,
                    "created_at": 1,
                    "run_created_at": 1,
                    "run_started_at": 1,
                    "conclusion": 1,
                }
            },
        ]

        return list(self.collection.aggregate(pipeline))

    def bulk_create_from_raw_builds(
        self,
        scenario_id: str,
        raw_build_data: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk create ingestion builds from raw build run data.

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
            doc = TrainingIngestionBuild(
                scenario_id=scenario_oid,
                raw_repo_id=build_data["raw_repo_id"],
                raw_build_run_id=build_data["raw_build_run_id"],
                ci_run_id=build_data.get("ci_run_id", ""),
                commit_sha=build_data.get("commit_sha", ""),
                repo_full_name=build_data.get("repo_full_name", ""),
                github_repo_id=build_data.get("github_repo_id"),
                status=IngestionStatus.PENDING,
                resource_status={},
                required_resources=build_data.get("required_resources", []),
            )
            documents.append(doc)

        inserted = self.insert_many(documents)
        return len(inserted)

    def update_status(
        self,
        ingestion_build_id: str,
        status: IngestionStatus,
        error_message: Optional[str] = None,
    ) -> Optional[TrainingIngestionBuild]:
        """Update ingestion build status."""
        updates: Dict[str, Any] = {"status": status.value}

        if status == IngestionStatus.INGESTING:
            updates["ingestion_started_at"] = datetime.utcnow()
        elif status == IngestionStatus.INGESTED:
            updates["ingested_at"] = datetime.utcnow()

        if error_message is not None:
            updates["ingestion_error"] = error_message

        return self.update_one(ingestion_build_id, updates)

    def update_resource_status(
        self,
        ingestion_build_id: str,
        resource_name: str,
        resource_status: ResourceStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update status for a specific resource.

        Args:
            ingestion_build_id: Ingestion build ID
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
            {"_id": self._to_object_id(ingestion_build_id)},
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

    def delete_by_scenario(self, scenario_id: str, session=None) -> int:
        """Delete all ingestion builds for a scenario."""
        return self.delete_many(
            {"scenario_id": self._to_object_id(scenario_id)}, session=session
        )

    def update_resource_batch(
        self,
        scenario_id: str,
        raw_repo_id: str,
        resource: str,
        status: ResourceStatus,
        error: Optional[str] = None,
    ) -> int:
        """
        Update resource status for all ingestion builds in a scenario/repo.
        Used when updating status for the whole batch (e.g., git_worktree checkout).
        """
        now = datetime.utcnow()
        query = {
            "scenario_id": self._to_object_id(scenario_id),
            "raw_repo_id": self._to_object_id(raw_repo_id),
            "status": IngestionStatus.INGESTING.value,
        }

        update_fields = {
            f"resource_status.{resource}.status": status.value,
        }
        if status == ResourceStatus.IN_PROGRESS:
            update_fields[f"resource_status.{resource}.started_at"] = now
        elif status in (ResourceStatus.COMPLETED, ResourceStatus.FAILED):
            update_fields[f"resource_status.{resource}.completed_at"] = now

        if error:
            update_fields[f"resource_status.{resource}.error"] = error

        result = self.collection.update_many(query, {"$set": update_fields})
        return result.modified_count

    def update_resource_by_commits(
        self,
        scenario_id: str,
        raw_repo_id: str,
        resource: str,
        commits: List[str],
        status: ResourceStatus,
        error: Optional[str] = None,
    ) -> int:
        """Update resource status for builds matching specific commits."""
        if not commits:
            return 0

        now = datetime.utcnow()
        query = {
            "scenario_id": self._to_object_id(scenario_id),
            "raw_repo_id": self._to_object_id(raw_repo_id),
            "commit_sha": {"$in": commits},
            "status": IngestionStatus.INGESTING.value,
        }

        update_fields = {
            f"resource_status.{resource}.status": status.value,
        }
        if status == ResourceStatus.IN_PROGRESS:
            update_fields[f"resource_status.{resource}.started_at"] = now
        elif status in (ResourceStatus.COMPLETED, ResourceStatus.FAILED):
            update_fields[f"resource_status.{resource}.completed_at"] = now

        if error:
            update_fields[f"resource_status.{resource}.error"] = error

        result = self.collection.update_many(query, {"$set": update_fields})
        return result.modified_count

    def update_resource_by_ci_run_ids(
        self,
        scenario_id: str,
        raw_repo_id: str,
        resource: str,
        ci_run_ids: List[str],
        status: ResourceStatus,
        error: Optional[str] = None,
    ) -> int:
        """Update resource status for builds matching specific CI run IDs."""
        if not ci_run_ids:
            return 0

        now = datetime.utcnow()
        query = {
            "scenario_id": self._to_object_id(scenario_id),
            "raw_repo_id": self._to_object_id(raw_repo_id),
            "ci_run_id": {"$in": ci_run_ids},
            "status": IngestionStatus.INGESTING.value,
        }

        update_fields = {
            f"resource_status.{resource}.status": status.value,
        }
        if status == ResourceStatus.IN_PROGRESS:
            update_fields[f"resource_status.{resource}.started_at"] = now
        elif status in (ResourceStatus.COMPLETED, ResourceStatus.FAILED):
            update_fields[f"resource_status.{resource}.completed_at"] = now

        if error:
            update_fields[f"resource_status.{resource}.error"] = error

        result = self.collection.update_many(query, {"$set": update_fields})
        return result.modified_count

    def get_build_ids_by_commits(
        self,
        scenario_id: str,
        commits: List[str],
    ) -> List[str]:
        """
        Get TrainingIngestionBuild IDs matching specific commit SHAs.

        Used by SSE events to send build_ids for frontend delta merge.

        Args:
            scenario_id: TrainingScenario ID
            commits: List of commit SHAs

        Returns:
            List of TrainingIngestionBuild IDs (as strings)
        """
        if not commits:
            return []

        docs = self.collection.find(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "commit_sha": {"$in": commits},
            },
            {"_id": 1},
        )
        return [str(doc["_id"]) for doc in docs]

    # ========== Task Failure Handling Methods ==========

    def mark_builds_failed_by_commits(
        self,
        scenario_id: str,
        commit_shas: List[str],
        error_message: str,
    ) -> int:
        """
        Mark builds as FAILED based on commit SHAs.

        Used by IngestionTask when a task fails and needs to mark
        affected builds based on the commits it was processing.

        Args:
            scenario_id: TrainingScenario ID
            commit_shas: List of commit SHAs whose builds should be marked
            error_message: Error message to store

        Returns:
            Number of builds marked as failed
        """
        if not commit_shas:
            return 0

        result = self.collection.update_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "commit_sha": {"$in": commit_shas},
                "status": IngestionStatus.INGESTING.value,
            },
            {
                "$set": {
                    "status": IngestionStatus.FAILED.value,
                    "ingestion_error": error_message[:500],
                }
            },
        )
        return result.modified_count

    def mark_all_ingesting_failed(
        self,
        scenario_id: str,
        error_message: str,
    ) -> int:
        """
        Mark ALL currently INGESTING builds as FAILED.

        Used when a repo-wide failure occurs (e.g., clone failed)
        that affects all builds for the scenario.

        Args:
            scenario_id: TrainingScenario ID
            error_message: Error message to store

        Returns:
            Number of builds marked as failed
        """
        result = self.collection.update_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "status": IngestionStatus.INGESTING.value,
            },
            {
                "$set": {
                    "status": IngestionStatus.FAILED.value,
                    "ingestion_error": error_message[:500],
                }
            },
        )
        return result.modified_count

    def update_status_by_ci_run_ids(
        self,
        scenario_id: str,
        ci_run_ids: List[str],
        from_status: str,
        updates: dict,
    ) -> int:
        """
        Update build status for builds matching specific CI run IDs.

        Used by IngestionTask to mark specific builds as FAILED on task failure.

        Args:
            scenario_id: TrainingScenario ID
            ci_run_ids: List of CI run IDs to update
            from_status: Current status to filter (e.g., INGESTING)
            updates: Fields to update (e.g., status, ingestion_error)

        Returns:
            Number of builds updated
        """
        if not ci_run_ids:
            return 0

        result = self.collection.update_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "status": from_status,
                "ci_run_id": {"$in": ci_run_ids},
            },
            {"$set": updates},
        )
        return result.modified_count

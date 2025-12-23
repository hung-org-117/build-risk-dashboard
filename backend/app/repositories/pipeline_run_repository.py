"""
Pipeline Run Repository - Database operations for pipeline execution tracking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.entities.pipeline_run import PipelineRun, PipelineStatus

from .base import BaseRepository


class PipelineRunRepository(BaseRepository[PipelineRun]):
    """Repository for PipelineRun entities."""

    def __init__(self, db):
        super().__init__(db, "pipeline_runs", PipelineRun)

    def find_by_correlation_id(self, correlation_id: str) -> Optional[PipelineRun]:
        """Find a pipeline run by its correlation ID."""
        return self.find_one({"correlation_id": correlation_id})

    def find_by_dataset(
        self,
        dataset_id: str,
        limit: int = 20,
    ) -> List[PipelineRun]:
        """Find all pipeline runs for a dataset."""
        return self.find_many(
            {"dataset_id": self._to_object_id(dataset_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def find_by_version(
        self,
        version_id: str,
        limit: int = 20,
    ) -> List[PipelineRun]:
        """Find all pipeline runs for a dataset version."""
        return self.find_many(
            {"version_id": self._to_object_id(version_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def find_by_repo_config(
        self,
        repo_config_id: str,
        limit: int = 20,
    ) -> List[PipelineRun]:
        """Find all pipeline runs for a model repo config."""
        return self.find_many(
            {"repo_config_id": self._to_object_id(repo_config_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def find_recent(
        self,
        pipeline_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple[List[PipelineRun], int]:
        """Find recent pipeline runs with optional filtering."""
        query: Dict[str, Any] = {}
        if pipeline_type:
            query["pipeline_type"] = pipeline_type
        if status:
            query["status"] = status

        return self.paginate(
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def update_status(
        self,
        correlation_id: str,
        status: PipelineStatus,
        error_message: Optional[str] = None,
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update pipeline run status."""
        update: Dict[str, Any] = {
            "status": status.value if isinstance(status, PipelineStatus) else status,
            "updated_at": datetime.now(timezone.utc),
        }

        if status in [
            PipelineStatus.COMPLETED,
            PipelineStatus.PARTIAL,
            PipelineStatus.FAILED,
            PipelineStatus.CANCELLED,
        ]:
            update["completed_at"] = datetime.now(timezone.utc)

        if error_message:
            update["error_message"] = error_message
        if result_summary:
            update["result_summary"] = result_summary

        result = self.collection.update_one(
            {"correlation_id": correlation_id},
            {"$set": update},
        )
        return result.modified_count > 0

    def update_phase(
        self,
        correlation_id: str,
        phase_name: str,
        phase_data: Dict[str, Any],
    ) -> bool:
        """Update a specific phase within the pipeline run."""
        # Try to update existing phase first
        result = self.collection.update_one(
            {"correlation_id": correlation_id, "phases.phase_name": phase_name},
            {"$set": {f"phases.$.{k}": v for k, v in phase_data.items()}},
        )

        if result.modified_count == 0:
            # Phase doesn't exist, push new one
            result = self.collection.update_one(
                {"correlation_id": correlation_id},
                {"$push": {"phases": {"phase_name": phase_name, **phase_data}}},
            )

        return result.modified_count > 0

    def start_phase(
        self,
        correlation_id: str,
        phase_name: str,
        total_items: int = 0,
    ) -> bool:
        """Start a phase within the pipeline run."""
        return self.update_phase(
            correlation_id,
            phase_name,
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "total_items": total_items,
            },
        )

    def complete_phase(
        self,
        correlation_id: str,
        phase_name: str,
        processed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Complete a phase with results."""
        phase_data: Dict[str, Any] = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc),
            "processed_items": processed,
            "failed_items": failed,
            "skipped_items": skipped,
        }
        if metadata:
            phase_data["metadata"] = metadata

        return self.update_phase(correlation_id, phase_name, phase_data)

    def fail_phase(
        self,
        correlation_id: str,
        phase_name: str,
        error: str,
    ) -> bool:
        """Mark a phase as failed."""
        # Use $push to add error to array
        self.collection.update_one(
            {"correlation_id": correlation_id, "phases.phase_name": phase_name},
            {"$push": {"phases.$.errors": error}},
        )

        return self.update_phase(
            correlation_id,
            phase_name,
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc),
            },
        )

    def increment_progress(
        self,
        correlation_id: str,
        processed_builds: int = 0,
        failed_builds: int = 0,
        processed_repos: int = 0,
    ) -> bool:
        """Increment build/repo processing counters."""
        update: Dict[str, int] = {}
        if processed_builds:
            update["processed_builds"] = processed_builds
        if failed_builds:
            update["failed_builds"] = failed_builds
        if processed_repos:
            update["processed_repos"] = processed_repos

        if not update:
            return False

        result = self.collection.update_one(
            {"correlation_id": correlation_id},
            {"$inc": update},
        )
        return result.modified_count > 0

    def set_totals(
        self,
        correlation_id: str,
        total_repos: int = 0,
        total_builds: int = 0,
    ) -> bool:
        """Set total counts for repos/builds."""
        update: Dict[str, int] = {}
        if total_repos:
            update["total_repos"] = total_repos
        if total_builds:
            update["total_builds"] = total_builds

        if not update:
            return False

        result = self.collection.update_one(
            {"correlation_id": correlation_id},
            {"$set": update},
        )
        return result.modified_count > 0

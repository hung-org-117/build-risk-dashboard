"""Repository for InitialScanJob entities"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from pymongo.database import Database

from app.models.entities.scan_job import InitialScanJob
from .base import BaseRepository


class ScanJobRepository(BaseRepository[InitialScanJob]):
    """Repository for scan job entities"""

    def __init__(self, db: Database):
        super().__init__(db, "scan_jobs", InitialScanJob)

    def create_job(self, repo_id: str | ObjectId) -> InitialScanJob:
        """Create a new scan job"""
        now = datetime.now(timezone.utc)
        doc = {
            "repo_id": self._to_object_id(repo_id),
            "status": "queued",
            "phase": "pending",
            "total_runs": 0,
            "processed_runs": 0,
            "created_at": now,
            "updated_at": now,
        }
        return self.insert_one(doc)

    def update_progress(
        self,
        job_id: str | ObjectId,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        total_runs: Optional[int] = None,
        processed_runs: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Optional[InitialScanJob]:
        """Update job progress"""
        updates = {"updated_at": datetime.now(timezone.utc)}
        if status:
            updates["status"] = status
            if status == "running" and "started_at" not in updates:
                # We might want to set started_at only once, but for now simple update
                pass
            if status in ["completed", "failed"]:
                updates["completed_at"] = datetime.now(timezone.utc)

        if phase:
            updates["phase"] = phase
        if total_runs is not None:
            updates["total_runs"] = total_runs
        if processed_runs is not None:
            updates["processed_runs"] = processed_runs
        if error:
            updates["error"] = error

        return self.update_one(job_id, updates)

    def get_active_job(self, repo_id: str | ObjectId) -> Optional[InitialScanJob]:
        """Get active scan job for a repo"""
        return self.find_one(
            {
                "repo_id": self._to_object_id(repo_id),
                "status": {"$in": ["queued", "running"]},
            }
        )

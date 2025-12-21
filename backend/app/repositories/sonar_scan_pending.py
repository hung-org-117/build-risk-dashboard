"""
SonarScanPending Repository - CRUD operations for pending SonarQube scans.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.sonar_scan_pending import ScanPendingStatus, SonarScanPending


class SonarScanPendingRepository:
    """Repository for SonarScanPending records."""

    def __init__(self, db: Database):
        self.db = db
        self.collection = db["sonar_scan_pending"]

    def insert_one(self, pending: SonarScanPending) -> SonarScanPending:
        """Insert a new pending scan record."""
        doc = pending.model_dump(by_alias=True, exclude={"id"})
        result = self.collection.insert_one(doc)
        pending.id = result.inserted_id
        return pending

    def find_by_version(
        self,
        version_id: ObjectId,
        status: Optional[ScanPendingStatus] = None,
    ) -> List[SonarScanPending]:
        """Find all scans for a version, optionally filtered by status."""
        query = {"dataset_version_id": version_id}
        if status:
            query["status"] = status.value
        cursor = self.collection.find(query).sort("created_at", -1)
        return [SonarScanPending(**doc) for doc in cursor]

    def find_by_version_and_commit(
        self,
        version_id: ObjectId,
        commit_sha: str,
    ) -> Optional[SonarScanPending]:
        """Find scan for specific version + commit."""
        doc = self.collection.find_one(
            {
                "dataset_version_id": version_id,
                "commit_sha": commit_sha,
            }
        )
        return SonarScanPending(**doc) if doc else None

    def find_by_component_key(self, component_key: str) -> Optional[SonarScanPending]:
        """Find pending scan by component key."""
        doc = self.collection.find_one({"component_key": component_key})
        return SonarScanPending(**doc) if doc else None

    def find_pending_by_component_key(
        self,
        component_key: str,
    ) -> Optional[SonarScanPending]:
        """Find only scanning (not completed) record by component key."""
        doc = self.collection.find_one(
            {
                "component_key": component_key,
                "status": {
                    "$in": [
                        ScanPendingStatus.PENDING.value,
                        ScanPendingStatus.SCANNING.value,
                    ]
                },
            }
        )
        return SonarScanPending(**doc) if doc else None

    def create_or_get(
        self,
        version_id: ObjectId,
        commit_sha: str,
        repo_full_name: str,
        component_key: str,
        repo_url: str,
        scan_config: Optional[dict] = None,
    ) -> SonarScanPending:
        """Create new scan record or return existing."""
        existing = self.find_by_version_and_commit(version_id, commit_sha)
        if existing:
            return existing

        scan = SonarScanPending(
            dataset_version_id=version_id,
            commit_sha=commit_sha,
            repo_full_name=repo_full_name,
            component_key=component_key,
            repo_url=repo_url,
            scan_config=scan_config,
            status=ScanPendingStatus.PENDING,
        )
        return self.insert_one(scan)

    def mark_scanning(self, scan_id: ObjectId) -> None:
        """Mark scan as in progress."""
        self.collection.update_one(
            {"_id": scan_id},
            {
                "$set": {
                    "status": ScanPendingStatus.SCANNING.value,
                    "started_at": datetime.now(timezone.utc),
                }
            },
        )

    def mark_completed(
        self,
        pending_id: ObjectId,
        metrics: dict,
        builds_affected: int = 0,
    ) -> None:
        """Mark a scan as completed with metrics."""
        self.collection.update_one(
            {"_id": pending_id},
            {
                "$set": {
                    "status": ScanPendingStatus.COMPLETED.value,
                    "metrics": metrics,
                    "builds_affected": builds_affected,
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": None,
                }
            },
        )

    def mark_failed(self, pending_id: ObjectId, error_message: str) -> None:
        """Mark a scan as failed."""
        self.collection.update_one(
            {"_id": pending_id},
            {
                "$set": {
                    "status": ScanPendingStatus.FAILED.value,
                    "error_message": error_message,
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )

    def increment_retry(self, scan_id: ObjectId) -> None:
        """Increment retry count and reset to pending."""
        self.collection.update_one(
            {"_id": scan_id},
            {
                "$inc": {"retry_count": 1},
                "$set": {
                    "status": ScanPendingStatus.PENDING.value,
                    "error_message": None,
                    "started_at": None,
                    "completed_at": None,
                },
            },
        )

    def get_failed_by_version(self, version_id: ObjectId) -> List[SonarScanPending]:
        """Get all failed scans for a version."""
        cursor = self.collection.find(
            {
                "dataset_version_id": version_id,
                "status": ScanPendingStatus.FAILED.value,
            }
        )
        return [SonarScanPending(**doc) for doc in cursor]

    def delete_old_scans(self, days: int = 30) -> int:
        """Delete completed scans older than specified days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = self.collection.delete_many(
            {
                "status": {
                    "$in": [
                        ScanPendingStatus.COMPLETED.value,
                        ScanPendingStatus.FAILED.value,
                    ]
                },
                "completed_at": {"$lt": cutoff},
            }
        )
        return result.deleted_count

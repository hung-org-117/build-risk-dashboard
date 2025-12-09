"""
SonarScanPending Repository - CRUD operations for pending SonarQube scans.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.sonar_scan_pending import SonarScanPending, ScanPendingStatus


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

    def find_by_component_key(self, component_key: str) -> Optional[SonarScanPending]:
        """Find pending scan by component key."""
        doc = self.collection.find_one({"component_key": component_key})
        return SonarScanPending(**doc) if doc else None

    def find_pending_by_component_key(
        self, component_key: str
    ) -> Optional[SonarScanPending]:
        """Find only scanning (not completed) record by component key."""
        doc = self.collection.find_one(
            {
                "component_key": component_key,
                "status": ScanPendingStatus.SCANNING.value,
            }
        )
        return SonarScanPending(**doc) if doc else None

    def find_completed_by_component_key(
        self, component_key: str
    ) -> Optional[SonarScanPending]:
        """Find completed scan with metrics by component key."""
        doc = self.collection.find_one(
            {
                "component_key": component_key,
                "status": ScanPendingStatus.COMPLETED.value,
            }
        )
        return SonarScanPending(**doc) if doc else None

    def is_pending(self, component_key: str) -> bool:
        """Check if a scan is currently in progress for this component."""
        return self.find_pending_by_component_key(component_key) is not None

    def mark_completed(
        self,
        pending_id: ObjectId,
        metrics: Dict,
    ) -> None:
        """Mark a scan as completed with metrics."""
        self.collection.update_one(
            {"_id": pending_id},
            {
                "$set": {
                    "status": ScanPendingStatus.COMPLETED.value,
                    "metrics": metrics,
                    "completed_at": datetime.now(timezone.utc),
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

    def find_by_build(
        self,
        build_id: ObjectId,
        build_type: str,
    ) -> Optional[SonarScanPending]:
        """Find pending scan for a specific build."""
        doc = self.collection.find_one(
            {
                "build_id": build_id,
                "build_type": build_type,
            }
        )
        return SonarScanPending(**doc) if doc else None

    def delete_old_scans(self, days: int = 30) -> int:
        """Delete completed scans older than specified days."""
        from datetime import timedelta

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

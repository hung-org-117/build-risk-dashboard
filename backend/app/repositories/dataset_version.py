from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.entities.dataset_version import DatasetVersion, VersionStatus
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class DatasetVersionRepository(BaseRepository[DatasetVersion]):
    """Repository for DatasetVersion entities."""

    COLLECTION_NAME = "dataset_versions"

    def __init__(self, db: Database):
        super().__init__(db, self.COLLECTION_NAME, DatasetVersion)

    def create(self, version: DatasetVersion) -> DatasetVersion:
        """Create a new dataset version."""
        data = version.model_dump(exclude={"id"})
        result = self.collection.insert_one(data)
        version.id = result.inserted_id
        return version

    def find_by_id(self, version_id: Union[str, ObjectId]) -> Optional[DatasetVersion]:
        """Find version by ID."""
        try:
            doc = self.collection.find_one({"_id": self.ensure_object_id(version_id)})
            if doc:
                return DatasetVersion(**doc)
            return None
        except (ValueError, TypeError):
            return None

    def find_by_dataset(
        self, dataset_id: Union[str, ObjectId], skip: int = 0, limit: int = 10
    ) -> tuple[List[DatasetVersion], int]:
        """Find all versions for a dataset, newest first, with pagination."""
        oid = self.ensure_object_id(dataset_id)
        query = {"dataset_id": oid}
        total = self.collection.count_documents(query)
        docs = (
            self.collection.find(query)
            .sort("version_number", -1)
            .skip(skip)
            .limit(limit)
        )
        return [DatasetVersion(**doc) for doc in docs], total

    def find_active_by_dataset(
        self, dataset_id: Union[str, ObjectId]
    ) -> Optional[DatasetVersion]:
        """Find running or pending version for a dataset."""
        oid = self.ensure_object_id(dataset_id)
        doc = self.collection.find_one(
            {
                "dataset_id": oid,
                "status": {"$in": [VersionStatus.QUEUED, VersionStatus.INGESTING]},
            }
        )
        if doc:
            return DatasetVersion(**doc)
        return None

    def find_latest_by_dataset(
        self, dataset_id: Union[str, ObjectId]
    ) -> Optional[DatasetVersion]:
        """Find the latest completed version for a dataset."""
        oid = self.ensure_object_id(dataset_id)
        doc = self.collection.find_one(
            {"dataset_id": oid, "status": VersionStatus.PROCESSED},
            sort=[("version_number", -1)],
        )
        if doc:
            return DatasetVersion(**doc)
        return None

    def get_next_version_number(self, dataset_id: Union[str, ObjectId]) -> int:
        """Get the next version number for a dataset."""
        oid = self.ensure_object_id(dataset_id)
        latest = self.collection.find_one(
            {"dataset_id": oid}, sort=[("version_number", -1)]
        )
        if latest:
            return latest.get("version_number", 0) + 1
        return 1

    def find_by_user(
        self,
        user_id: Union[str, ObjectId],
        skip: int = 0,
        limit: int = 20,
    ) -> List[DatasetVersion]:
        """Find versions for a user."""
        oid = self.ensure_object_id(user_id)
        docs = (
            self.collection.find({"user_id": oid})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [DatasetVersion(**doc) for doc in docs]

    def update_one(
        self, version_id: Union[str, ObjectId], updates: Dict[str, Any]
    ) -> bool:
        """Update a version by ID."""
        updates["updated_at"] = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)}, {"$set": updates}
        )
        return result.modified_count > 0

    def update_build_progress(
        self,
        version_id: Union[str, ObjectId],
        builds_features_extracted: int,
        builds_extraction_failed: int,
    ) -> bool:
        """Update version build progress atomically."""
        updates: Dict[str, Any] = {
            "builds_features_extracted": builds_features_extracted,
            "builds_extraction_failed": builds_extraction_failed,
            "updated_at": datetime.now(timezone.utc),
        }

        update_ops: Dict[str, Any] = {"$set": updates}

        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)}, update_ops
        )
        return result.modified_count > 0

    def increment_builds(
        self,
        version_id: Union[str, ObjectId],
        builds_features_extracted: int = 0,
        builds_extraction_failed: int = 0,
    ) -> bool:
        """Increment version build counters atomically using $inc.

        Used for sequential processing where each task adds to the total.
        """
        inc_ops: Dict[str, int] = {}
        if builds_features_extracted:
            inc_ops["builds_features_extracted"] = builds_features_extracted
        if builds_extraction_failed:
            inc_ops["builds_extraction_failed"] = builds_extraction_failed

        if not inc_ops:
            return False

        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$inc": inc_ops,
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.modified_count > 0

    def increment_builds_features_extracted(
        self, version_id: Union[str, ObjectId], count: int = 1
    ) -> bool:
        """Increment builds_features_extracted counter by 1 (or specified count)."""
        return self.increment_builds(version_id, builds_features_extracted=count)

    def increment_scans_completed(
        self, version_id: Union[str, ObjectId], count: int = 1
    ) -> bool:
        """Increment scans_completed counter atomically."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$inc": {"scans_completed": count},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.modified_count > 0

    def increment_scans_failed(
        self, version_id: Union[str, ObjectId], count: int = 1
    ) -> bool:
        """Increment scans_failed counter atomically."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$inc": {"scans_failed": count},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.modified_count > 0

    def mark_feature_extraction_completed(
        self, version_id: Union[str, ObjectId]
    ) -> bool:
        """Mark feature extraction as completed."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$set": {
                    "feature_extraction_completed": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    def mark_scan_extraction_completed(self, version_id: Union[str, ObjectId]) -> bool:
        """Mark scan extraction as completed."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$set": {
                    "scan_extraction_completed": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    def mark_enrichment_notified(self, version_id: Union[str, ObjectId]) -> bool:
        """Mark that enrichment notification has been sent."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$set": {
                    "enrichment_notified": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    def mark_started(
        self, version_id: Union[str, ObjectId], task_id: Optional[str] = None
    ) -> bool:
        """Mark version as started processing."""
        updates: Dict[str, Any] = {
            "status": VersionStatus.PROCESSING,
            "started_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if task_id:
            updates["task_id"] = task_id

        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)}, {"$set": updates}
        )
        return result.modified_count > 0

    def mark_completed(self, version_id: Union[str, ObjectId]) -> bool:
        """Mark version as completed."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$set": {
                    "status": VersionStatus.PROCESSED,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    def mark_failed(self, version_id: Union[str, ObjectId], error: str) -> bool:
        """Mark version as failed."""
        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {
                "$set": {
                    "status": VersionStatus.FAILED,
                    "error_message": error,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    def mark_status(self, version_id: Union[str, ObjectId], status: str) -> bool:
        """Mark version with a specific status.

        Args:
            version_id: Version ID to update
            status: Target status value (e.g., 'processed', 'failed')
        """
        updates: Dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        # Set completed_at for terminal statuses
        if status in (VersionStatus.PROCESSED.value, VersionStatus.FAILED.value):
            updates["completed_at"] = datetime.now(timezone.utc)

        result = self.collection.update_one(
            {"_id": self.ensure_object_id(version_id)},
            {"$set": updates},
        )
        return result.modified_count > 0

    def delete(
        self, version_id: Union[str, ObjectId], session: "ClientSession | None" = None
    ) -> bool:
        """Delete a version.

        Args:
            version_id: Version ID to delete
            session: Optional MongoDB session for transaction support
        """
        result = self.collection.delete_one(
            {"_id": self.ensure_object_id(version_id)}, session=session
        )
        return result.deleted_count > 0

    def delete_by_dataset(
        self, dataset_id: Union[str, ObjectId], session: "ClientSession | None" = None
    ) -> int:
        """Delete all versions for a dataset.

        Args:
            dataset_id: Dataset ID to delete versions for
            session: Optional MongoDB session for transaction support
        """
        oid = self.ensure_object_id(dataset_id)
        result = self.collection.delete_many({"dataset_id": oid}, session=session)
        return result.deleted_count

    def count_by_dataset(self, dataset_id: Union[str, ObjectId]) -> int:
        """Count versions for a dataset."""
        oid = self.ensure_object_id(dataset_id)
        return self.collection.count_documents({"dataset_id": oid})

    def count_completed_by_dataset(self, dataset_id: Union[str, ObjectId]) -> int:
        """Count completed versions for a dataset."""
        oid = self.ensure_object_id(dataset_id)
        return self.collection.count_documents(
            {"dataset_id": oid, "status": VersionStatus.PROCESSED}
        )

"""
Data Quality Repository - Database operations for quality evaluation reports.
"""

from typing import List, Optional

from bson import ObjectId

from app.entities.data_quality import DataQualityReport

from .base import BaseRepository


class DataQualityRepository(BaseRepository[DataQualityReport]):
    """Repository for data quality reports."""

    def __init__(self, db):
        super().__init__(db, "data_quality_reports", DataQualityReport)

    def find_by_version(self, version_id: str) -> Optional[DataQualityReport]:
        """
        Get the latest quality report for a version.

        Args:
            version_id: Dataset version ID

        Returns:
            Latest DataQualityReport or None
        """
        return self.find_one(
            {"version_id": self._to_object_id(version_id)},
        )

    def find_all_by_version(self, version_id: str, limit: int = 10) -> List[DataQualityReport]:
        """
        Get report history for a version.

        Args:
            version_id: Dataset version ID
            limit: Maximum number of reports to return

        Returns:
            List of DataQualityReport ordered by created_at desc
        """
        return self.find_many(
            {"version_id": self._to_object_id(version_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def find_by_dataset(self, dataset_id: str, limit: int = 50) -> List[DataQualityReport]:
        """
        Get all quality reports for a dataset.

        Args:
            dataset_id: Dataset ID
            limit: Maximum number of reports

        Returns:
            List of DataQualityReport ordered by created_at desc
        """
        return self.find_many(
            {"dataset_id": self._to_object_id(dataset_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def delete_by_version(self, version_id: str, session=None) -> int:
        """
        Delete all reports for a version (cleanup).

        Args:
            version_id: Dataset version ID
            session: Optional MongoDB session for transactions

        Returns:
            Number of deleted documents
        """
        result = self.collection.delete_many(
            {"version_id": ObjectId(version_id)},
            session=session,
        )
        return result.deleted_count

    def find_pending_or_running(self, version_id: str) -> Optional[DataQualityReport]:
        """
        Find any pending or running evaluation for a version.

        Args:
            version_id: Dataset version ID

        Returns:
            DataQualityReport if found, None otherwise
        """
        return self.find_one(
            {
                "version_id": self._to_object_id(version_id),
                "status": {"$in": ["pending", "running"]},
            }
        )

    def delete_by_dataset(self, dataset_id: str, session=None) -> int:
        """
        Delete all quality reports for a dataset (cleanup).

        Args:
            dataset_id: Dataset ID
            session: Optional MongoDB session for transactions

        Returns:
            Number of deleted documents
        """
        result = self.collection.delete_many(
            {"dataset_id": ObjectId(dataset_id)},
            session=session,
        )
        return result.deleted_count

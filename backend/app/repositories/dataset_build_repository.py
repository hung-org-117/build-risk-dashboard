from __future__ import annotations

from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.entities.dataset_build import DatasetBuild

from .base import BaseRepository


class DatasetBuildRepository(BaseRepository[DatasetBuild]):
    """Repository for dataset_builds collection."""

    def __init__(self, db: Database):
        super().__init__(db, "dataset_builds", DatasetBuild)

    def delete_by_dataset(
        self, dataset_id: str, session: "ClientSession | None" = None
    ) -> int:
        """Delete all builds for a dataset.

        Args:
            dataset_id: Dataset ID to delete builds for
            session: Optional MongoDB session for transaction support
        """
        oid = self._to_object_id(dataset_id)
        if not oid:
            return 0
        return self.delete_many({"dataset_id": oid}, session=session)

    def iterate_validated_builds(
        self,
        dataset_id: str,
        batch_size: int = 1000,
    ):
        """
        Iterate validated builds using cursor pagination.

        Yields batches of builds to avoid loading all into memory.
        Uses _id-based cursor pagination for efficiency with large datasets.

        Args:
            dataset_id: Dataset ID to query
            batch_size: Number of builds per batch

        Yields:
            List[DatasetBuild]: Batches of builds
        """
        oid = self._to_object_id(dataset_id)
        if not oid:
            return

        base_query = {"dataset_id": oid, "status": "found"}

        last_id = None
        while True:
            query = base_query.copy()
            if last_id:
                query["_id"] = {"$gt": last_id}

            cursor = self.collection.find(query).sort("_id", 1).limit(batch_size)
            batch = [DatasetBuild(**doc) for doc in cursor]

            if not batch:
                break

            yield batch
            last_id = batch[-1].id

    def find_found_builds_by_repo(
        self, dataset_id: str, raw_repo_id: str
    ) -> list[DatasetBuild]:
        """Find found builds for a specific raw repo in a dataset."""
        oid_ds = self._to_object_id(dataset_id)
        oid_repo = self._to_object_id(raw_repo_id)
        if not oid_ds or not oid_repo:
            return []
        return self.find_many(
            {"dataset_id": oid_ds, "raw_repo_id": oid_repo, "status": "found"}
        )

    def count_by_query(self, query: dict) -> int:
        """Count documents matching the query."""
        return self.count(query)

    def iterate_builds_with_run_ids_paginated(
        self,
        dataset_id: str,
        batch_size: int = 1000,
    ):
        """
        Iterate validated builds with raw_run_id using cursor pagination.

        Yields batches of builds to avoid loading all into memory.
        Uses _id-based cursor pagination for efficiency with large datasets.

        Args:
            dataset_id: Dataset ID to query
            batch_size: Number of builds per batch

        Yields:
            List[DatasetBuild]: Batches of builds
        """
        oid = self._to_object_id(dataset_id)
        if not oid:
            return

        base_query = {
            "dataset_id": oid,
            "status": "found",
            "raw_run_id": {"$ne": None},
        }

        last_id = None
        while True:
            query = base_query.copy()
            if last_id:
                query["_id"] = {"$gt": last_id}

            # Fetch batch with _id sort for cursor pagination
            cursor = self.collection.find(query).sort("_id", 1).limit(batch_size)
            batch = [DatasetBuild(**doc) for doc in cursor]

            if not batch:
                break

            yield batch
            last_id = batch[-1].id

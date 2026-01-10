"""Repository for SourceBuild entities."""

from __future__ import annotations

from typing import List, Optional

from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.entities.source_build import SourceBuild, SourceBuildStatus
from app.repositories.base import BaseRepository


class SourceBuildRepository(BaseRepository[SourceBuild]):
    """Repository for SourceBuild entity (tracks builds during source validation)."""

    def __init__(self, db: Database):
        super().__init__(db, "source_builds", SourceBuild)

    def find_by_source(
        self,
        source_id: str,
        status: Optional[SourceBuildStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceBuild]:
        """Get all builds for a source with optional status filter."""
        query = {"source_id": self._to_object_id(source_id)}
        if status:
            query["status"] = status.value
        return self.find_many(query, skip=skip, limit=limit)

    def count_by_source(
        self, source_id: str, status: Optional[SourceBuildStatus] = None
    ) -> int:
        """Count builds for a source."""
        query = {"source_id": self._to_object_id(source_id)}
        if status:
            query["status"] = status.value
        return self.collection.count_documents(query)

    def count_by_status(self, source_id: str) -> dict:
        """Get count of builds by status for a source."""
        pipeline = [
            {"$match": {"source_id": self._to_object_id(source_id)}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        results = list(self.collection.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in results}

    def bulk_create(
        self, builds: List[SourceBuild], session: Optional[ClientSession] = None
    ) -> int:
        """Bulk insert builds."""
        if not builds:
            return 0
        docs = [b.model_dump(by_alias=True) for b in builds]
        result = self.collection.insert_many(docs, session=session)
        return len(result.inserted_ids)

    def delete_by_source(
        self, source_id: str, session: Optional[ClientSession] = None
    ) -> int:
        """Delete all builds for a source."""
        return self.delete_many(
            {"source_id": self._to_object_id(source_id)}, session=session
        )

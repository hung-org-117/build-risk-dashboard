"""Repository for SourceRepoStats entities."""

from __future__ import annotations

from typing import List, Optional

from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.entities.source_repo_stats import SourceRepoStats
from app.repositories.base import BaseRepository


class SourceRepoStatsRepository(BaseRepository[SourceRepoStats]):
    """Repository for SourceRepoStats entity."""

    def __init__(self, db: Database):
        super().__init__(db, "source_repo_stats", SourceRepoStats)

    def find_by_source(self, source_id: str) -> List[SourceRepoStats]:
        """Get all repo stats for a source."""
        return self.find_many({"source_id": self._to_object_id(source_id)})

    def find_by_source_and_repo(
        self, source_id: str, raw_repo_id: str
    ) -> Optional[SourceRepoStats]:
        """Get stats for specific repo in source."""
        return self.find_one(
            {
                "source_id": self._to_object_id(source_id),
                "raw_repo_id": self._to_object_id(raw_repo_id),
            }
        )

    def upsert_by_source_and_repo(
        self, source_id: str, raw_repo_id: str, **data
    ) -> Optional[SourceRepoStats]:
        """Create or update repo stats."""
        query = {
            "source_id": self._to_object_id(source_id),
            "raw_repo_id": self._to_object_id(raw_repo_id),
        }
        update_data = {**query, **data}
        return self.find_one_and_update(
            query=query,
            update={"$set": update_data},
            upsert=True,
        )

    def delete_by_source(
        self, source_id: str, session: Optional[ClientSession] = None
    ) -> int:
        """Delete all repo stats for a source."""
        return self.delete_many(
            {"source_id": self._to_object_id(source_id)}, session=session
        )

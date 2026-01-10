"""Repository for BuildSource entities."""

from typing import Any, Dict, Optional

from pymongo.database import Database

from app.entities.build_source import BuildSource

from .base import BaseRepository


class BuildSourceRepository(BaseRepository[BuildSource]):
    """MongoDB repository for build sources (CSV uploads)."""

    def __init__(self, db: Database):
        super().__init__(db, "build_sources", BuildSource)

    def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 0,
        q: Optional[str] = None,
    ) -> tuple[list[BuildSource], int]:
        """List build sources for a user with optional search."""
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = self._to_object_id(user_id)

        if q:
            query["$or"] = [
                {"name": {"$regex": q, "$options": "i"}},
                {"file_name": {"$regex": q, "$options": "i"}},
            ]

        return self.paginate(
            query,
            sort=[("updated_at", -1), ("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def count_by_filter(self, user_id: Optional[str] = None) -> int:
        """Count build sources with optional user filter."""
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = self._to_object_id(user_id)
        return self.collection.count_documents(query)

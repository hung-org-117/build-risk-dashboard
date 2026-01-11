"""Repository for BuildSource entities."""

from typing import Any, Dict, Optional

from pymongo.database import Database

from app.entities.build_source import BuildSource

from .base import BaseRepository


class BuildSourceRepository(BaseRepository[BuildSource]):
    """MongoDB repository for build sources (CSV uploads)."""

    def __init__(self, db: Database):
        super().__init__(db, "build_sources", BuildSource)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 0,
        q: Optional[str] = None,
    ) -> tuple[list[BuildSource], int]:
        """List all build sources (shared among admins)."""
        query: Dict[str, Any] = {}

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

    def count_all(self) -> int:
        """Count all build sources."""
        return self.collection.count_documents({})

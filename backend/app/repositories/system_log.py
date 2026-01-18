"""Repository for SystemLog entities (application logs stored in MongoDB)."""

from typing import Any, Dict, List, Optional, Tuple

from app.entities.system_log import SystemLog
from app.repositories.base import BaseRepository


class SystemLogRepository(BaseRepository[SystemLog]):
    """Repository for SystemLog entities - application monitoring logs."""

    def __init__(self, db) -> None:
        super().__init__(db, "system_logs", SystemLog)

    def find_recent(
        self,
        skip: int = 0,
        limit: int = 100,
        level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Tuple[List[SystemLog], int]:
        """
        Find recent system logs with filtering and pagination.

        Args:
            skip: Pagination offset
            limit: Max results to return
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
            source: Filter by source component (partial match)

        Returns:
            Tuple of (logs list, total count)
        """
        query: Dict[str, Any] = {}
        if level:
            query["level"] = level.upper()
        if source:
            query["source"] = {"$regex": source, "$options": "i"}

        return self.paginate(query, sort=[("timestamp", -1)], skip=skip, limit=limit)

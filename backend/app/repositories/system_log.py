"""Repository for SystemLog entities (application logs stored in MongoDB)."""

from datetime import datetime
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

    def find_for_export(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10000,
    ) -> List[SystemLog]:
        """
        Find logs for export with date range filtering.

        Args:
            level: Filter by log level
            source: Filter by source component
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            limit: Max logs to export

        Returns:
            List of SystemLog entities
        """
        query: Dict[str, Any] = {}
        if level:
            query["level"] = level.upper()
        if source:
            query["source"] = {"$regex": source, "$options": "i"}
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        return self.find_many(query, sort=[("timestamp", -1)], limit=limit)

    def get_cursor_for_export(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        batch_size: int = 100,
        limit: int = 10000,
    ):
        """
        Get a MongoDB cursor for streaming export.

        Args:
            level: Filter by log level
            source: Filter by source component
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            batch_size: Cursor batch size
            limit: Max logs to export

        Returns:
            MongoDB cursor for iteration
        """
        query: Dict[str, Any] = {}
        if level:
            query["level"] = level.upper()
        if source:
            query["source"] = {"$regex": source, "$options": "i"}
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        return self.collection.find(query).sort("timestamp", -1).batch_size(batch_size).limit(limit)

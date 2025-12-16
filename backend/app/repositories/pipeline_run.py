"""
Pipeline Run Repository - Database operations for pipeline execution tracking.
"""

from typing import Any, Dict, List, Optional, Tuple

from .base import BaseRepository
from app.entities.pipeline_run import PipelineRun


class PipelineRunRepository(BaseRepository[PipelineRun]):
    """Repository for PipelineRun entities."""

    def __init__(self, db):
        super().__init__(db, "pipeline_runs", PipelineRun)

    def find_recent(
        self,
        limit: int = 50,
        skip: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[PipelineRun], int]:
        """
        Find recent pipeline runs with optional status filter.

        Args:
            limit: Maximum number of runs to return
            skip: Number of runs to skip (for pagination)
            status: Optional status filter

        Returns:
            Tuple of (list of runs, total count)
        """
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status

        return self.paginate(
            query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def find_by_repo(
        self,
        repo_id: str,
        limit: int = 20,
    ) -> List[PipelineRun]:
        """Find recent runs for a specific repository."""
        return self.find_many(
            {"repo_id": self._to_object_id(repo_id)},
            sort=[("created_at", -1)],
            limit=limit,
        )

    def find_by_build_sample(self, build_sample_id: str) -> Optional[PipelineRun]:
        """Find a run by build sample ID."""
        return self.find_one({"build_sample_id": self._to_object_id(build_sample_id)})

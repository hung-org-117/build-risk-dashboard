"""
Build Service - Query RawBuildRun as primary source with ModelTrainingBuild enrichment.

Flow:
1. Query raw_build_runs (available immediately after ingestion)
2. Left join with model_training_builds (optional - after processing)
3. Return merged data
"""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.dtos.build import BuildDetail, BuildListResponse, BuildSummary


class BuildService:
    """Service for querying builds with RawBuildRun as primary source."""

    def __init__(self, db: Database):
        self.db = db

    def get_builds_by_repo(
        self,
        repo_id: str,
        skip: int = 0,
        limit: int = 20,
        q: Optional[str] = None,
        extraction_status: Optional[str] = None,
    ) -> BuildListResponse:
        """
        Get builds for a repository.

        Args:
            repo_id: ModelRepoConfig._id or raw_repo_id
            skip: Pagination offset
            limit: Page size
            q: Search query (build number, commit sha, conclusion)
            extraction_status: Filter by extraction status (pending/completed/failed/not_started)
        """
        # Get raw_repo_id from model_repo_config if needed
        raw_repo_id = self._resolve_raw_repo_id(repo_id)
        if not raw_repo_id:
            return BuildListResponse(items=[], total=0, page=1, size=limit)

        # Build query for raw_build_runs
        query: Dict[str, Any] = {"raw_repo_id": raw_repo_id}

        if q:
            or_conditions = []
            if q.isdigit():
                or_conditions.append({"build_number": int(q)})
            or_conditions.append({"commit_sha": {"$regex": q, "$options": "i"}})
            query["$or"] = or_conditions

        # Get raw builds
        total = self.db.raw_build_runs.count_documents(query)
        raw_cursor = (
            self.db.raw_build_runs.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        raw_builds = list(raw_cursor)

        if not raw_builds:
            return BuildListResponse(
                items=[], total=total, page=skip // limit + 1, size=limit
            )

        # Get corresponding ModelTrainingBuilds
        raw_ids = [b["_id"] for b in raw_builds]
        training_cursor = self.db.model_training_builds.find(
            {"raw_workflow_run_id": {"$in": raw_ids}}
        )
        training_map = {doc["raw_workflow_run_id"]: doc for doc in training_cursor}

        # Build response items
        items = []
        for raw in raw_builds:
            training = training_map.get(raw["_id"])

            # Apply extraction_status filter if specified
            if extraction_status:
                if extraction_status == "not_started" and training is not None:
                    continue
                elif extraction_status != "not_started":
                    if (
                        training is None
                        or training.get("extraction_status") != extraction_status
                    ):
                        continue

            items.append(
                BuildSummary(
                    _id=str(raw["_id"]),
                    build_number=raw.get("build_number"),
                    build_id=raw.get("build_id", ""),
                    conclusion=raw.get("conclusion", "unknown"),
                    commit_sha=raw.get("commit_sha", ""),
                    branch=raw.get("branch", ""),
                    created_at=raw.get("created_at"),
                    completed_at=raw.get("completed_at"),
                    duration_seconds=raw.get("duration_seconds"),
                    jobs_count=raw.get("jobs_count", 0),
                    web_url=raw.get("web_url"),
                    logs_available=raw.get("logs_available"),
                    logs_expired=raw.get("logs_expired", False),
                    # Training enrichment
                    has_training_data=training is not None,
                    training_build_id=str(training["_id"]) if training else None,
                    extraction_status=(
                        training.get("extraction_status") if training else None
                    ),
                    feature_count=training.get("feature_count", 0) if training else 0,
                    extraction_error=(
                        training.get("extraction_error") if training else None
                    ),
                )
            )

        # Adjust total if filtering by extraction_status (need to recount)
        if extraction_status:
            total = len(items)

        return BuildListResponse(
            items=items,
            total=total,
            page=skip // limit + 1,
            size=limit,
        )

    def get_build_detail(self, build_id: str) -> Optional[BuildDetail]:
        """
        Get detailed build info by RawBuildRun._id.

        Args:
            build_id: RawBuildRun._id (MongoDB ObjectId string)
        """
        try:
            oid = ObjectId(build_id)
        except Exception:
            return None

        raw = self.db.raw_build_runs.find_one({"_id": oid})
        if not raw:
            return None

        # Get training data if exists
        training = self.db.model_training_builds.find_one({"raw_workflow_run_id": oid})

        return BuildDetail(
            _id=str(raw["_id"]),
            build_number=raw.get("build_number"),
            build_id=raw.get("build_id", ""),
            conclusion=raw.get("conclusion", "unknown"),
            commit_sha=raw.get("commit_sha", ""),
            branch=raw.get("branch", ""),
            commit_message=raw.get("commit_message"),
            commit_author=raw.get("commit_author"),
            created_at=raw.get("created_at"),
            started_at=raw.get("started_at"),
            completed_at=raw.get("completed_at"),
            duration_seconds=raw.get("duration_seconds"),
            jobs_count=raw.get("jobs_count", 0),
            jobs_metadata=raw.get("jobs_metadata", []),
            web_url=raw.get("web_url"),
            provider=raw.get("provider", "github_actions"),
            logs_available=raw.get("logs_available"),
            logs_expired=raw.get("logs_expired", False),
            # Training enrichment
            has_training_data=training is not None,
            training_build_id=str(training["_id"]) if training else None,
            extraction_status=training.get("extraction_status") if training else None,
            feature_count=training.get("feature_count", 0) if training else 0,
            extraction_error=training.get("extraction_error") if training else None,
            features=training.get("features", {}) if training else {},
        )

    def get_recent_builds(self, limit: int = 10) -> List[BuildSummary]:
        """Get most recent builds across all repos."""
        raw_cursor = self.db.raw_build_runs.find({}).sort("created_at", -1).limit(limit)
        raw_builds = list(raw_cursor)

        if not raw_builds:
            return []

        # Get training data
        raw_ids = [b["_id"] for b in raw_builds]
        training_cursor = self.db.model_training_builds.find(
            {"raw_workflow_run_id": {"$in": raw_ids}}
        )
        training_map = {doc["raw_workflow_run_id"]: doc for doc in training_cursor}

        items = []
        for raw in raw_builds:
            training = training_map.get(raw["_id"])
            items.append(
                BuildSummary(
                    _id=str(raw["_id"]),
                    build_number=raw.get("build_number"),
                    build_id=raw.get("build_id", ""),
                    conclusion=raw.get("conclusion", "unknown"),
                    commit_sha=raw.get("commit_sha", ""),
                    branch=raw.get("branch", ""),
                    created_at=raw.get("created_at"),
                    completed_at=raw.get("completed_at"),
                    duration_seconds=raw.get("duration_seconds"),
                    jobs_count=raw.get("jobs_count", 0),
                    web_url=raw.get("web_url"),
                    logs_available=raw.get("logs_available"),
                    logs_expired=raw.get("logs_expired", False),
                    has_training_data=training is not None,
                    training_build_id=str(training["_id"]) if training else None,
                    extraction_status=(
                        training.get("extraction_status") if training else None
                    ),
                    feature_count=training.get("feature_count", 0) if training else 0,
                    extraction_error=(
                        training.get("extraction_error") if training else None
                    ),
                )
            )
        return items

    def _resolve_raw_repo_id(self, repo_id: str) -> Optional[ObjectId]:
        """
        Resolve raw_repo_id from either ModelRepoConfig._id or direct raw_repo_id.
        """
        try:
            oid = ObjectId(repo_id)
        except Exception:
            return None

        # First try as ModelRepoConfig
        config = self.db.model_repo_configs.find_one({"_id": oid})
        if config:
            return config.get("raw_repo_id")

        # Fallback to direct raw_repo_id
        raw_repo = self.db.raw_repositories.find_one({"_id": oid})
        if raw_repo:
            return oid

        return None

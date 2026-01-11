from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from app.entities.base import validate_object_id
from app.entities.raw_build_run import RawBuildRun
from app.repositories.base import BaseRepository


class RawBuildRunRepository(BaseRepository[RawBuildRun]):
    """Repository for RawBuildRun entities - shared across all flows."""

    def __init__(self, db) -> None:
        super().__init__(db, "raw_build_runs", RawBuildRun)

    def find_by_business_key(
        self,
        raw_repo_id: str,
        build_id: str,
        provider: str,
    ) -> Optional[RawBuildRun]:
        oid = validate_object_id(raw_repo_id)
        if not oid:
            return None
        doc = self.collection.find_one(
            {
                "raw_repo_id": oid,
                "ci_run_id": build_id,
                "provider": provider,
            }
        )
        return RawBuildRun(**doc) if doc else None

    def find_by_build_id(
        self,
        raw_repo_id: ObjectId,
        build_id: str,
    ) -> Optional[RawBuildRun]:
        doc = self.collection.find_one(
            {
                "raw_repo_id": raw_repo_id,
                "ci_run_id": build_id,
            }
        )
        return RawBuildRun(**doc) if doc else None

    def find_by_repo_and_build_id(
        self,
        repo_id: str | ObjectId,
        build_id: str,
    ) -> Optional[RawBuildRun]:
        """Convenience method - accepts string repo_id for compatibility."""
        return self.find_by_build_id(self.ensure_object_id(repo_id), build_id)

    def find_by_commit_or_effective_sha(
        self,
        raw_repo_id: str,
        commit_sha: str,
    ) -> Optional[RawBuildRun]:
        """Find a build run by repo and commit SHA or effective SHA."""
        doc = self.collection.find_one(
            {
                "raw_repo_id": validate_object_id(raw_repo_id),
                "$or": [
                    {"commit_sha": commit_sha},
                    {"effective_sha": commit_sha},
                ],
            }
        )
        return RawBuildRun(**doc) if doc else None

    def list_by_repo(
        self,
        raw_repo_id: ObjectId,
        skip: int = 0,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> tuple[List[RawBuildRun], int]:
        """List build runs for a repository with pagination."""
        query: Dict[str, Any] = {"raw_repo_id": raw_repo_id}
        if since:
            query["created_at"] = {"$gte": since}

        return self.paginate(query, sort=[("created_at", -1)], skip=skip, limit=limit)

    def find_ids_by_build_ids(
        self,
        raw_repo_id: ObjectId,
        build_ids: List[str],
        provider: str,
    ) -> List[Dict[str, Any]]:
        """
        Batch query using $in to find multiple builds efficiently.
        Returns list of dicts with _id, commit_sha, effective_sha for each found build.
        """
        if not build_ids:
            return []

        cursor = self.collection.find(
            {
                "raw_repo_id": raw_repo_id,
                "ci_run_id": {"$in": build_ids},
                "provider": provider,
            },
            {
                "_id": 1,
                "commit_sha": 1,
                "effective_sha": 1,
            },  # Projection - only needed fields
        )
        return list(cursor)

    def upsert_by_business_key(
        self,
        raw_repo_id: ObjectId,
        build_id: str,
        provider: str,
        **kwargs,
    ) -> RawBuildRun:
        """
        Upsert by business key (raw_repo_id + build_id + provider).

        Uses atomic find_one_and_update for thread safety.
        This method ensures deduplication when the same build is
        fetched from both model flow and dataset flow.

        Auto-populates effective_sha from commit_sha if not explicitly provided,
        ensuring effective_sha is always set for downstream processing.
        """
        # Auto-populate effective_sha from commit_sha if not provided
        # This ensures effective_sha is always set for all builds
        if "effective_sha" not in kwargs and "commit_sha" in kwargs:
            kwargs["effective_sha"] = kwargs["commit_sha"]

        update_data = {
            "raw_repo_id": raw_repo_id,
            "ci_run_id": build_id,
            "provider": provider,
            **{k: v for k, v in kwargs.items() if v is not None},
        }

        doc = self.collection.find_one_and_update(
            {"raw_repo_id": raw_repo_id, "ci_run_id": build_id, "provider": provider},
            {"$set": update_data},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return RawBuildRun(**doc)

    def get_latest_run(
        self,
        raw_repo_id: ObjectId,
    ) -> Optional[RawBuildRun]:
        """Get the most recent build run for a repository."""
        doc = (
            self.collection.find({"raw_repo_id": raw_repo_id})
            .sort("created_at", -1)
            .limit(1)
        )
        docs = list(doc)
        return RawBuildRun(**docs[0]) if docs else None

    def count_by_repo(self, raw_repo_id: ObjectId) -> int:
        """Count build runs for a repository."""
        return self.collection.count_documents({"raw_repo_id": raw_repo_id})

    def update_effective_sha(self, build_run_id: ObjectId, effective_sha: str) -> bool:
        """Update effective_sha for a build run (used for replayed fork commits)."""
        result = self.collection.update_one(
            {"_id": build_run_id},
            {"$set": {"effective_sha": effective_sha}},
        )
        return result.modified_count > 0

    def find_metadata_by_ids(
        self,
        build_run_ids: List[ObjectId],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Find multiple build runs by IDs and return display metadata.

        Used by monitoring service to display build info in audit logs.

        Args:
            build_run_ids: List of RawBuildRun ObjectIds

        Returns:
            Dict mapping build_run_id string to metadata dict with:
            - build_number: Sequential build number
            - branch: Branch name
            - event: CI event type (from raw_data)
            - workflow_name: Workflow name (from raw_data)
        """
        if not build_run_ids:
            return {}

        cursor = self.collection.find(
            {"_id": {"$in": build_run_ids}},
            {"_id": 1, "build_number": 1, "branch": 1, "raw_data": 1},
        )

        result: Dict[str, Dict[str, Any]] = {}
        for doc in cursor:
            raw_data = doc.get("raw_data", {})
            result[str(doc["_id"])] = {
                "build_number": doc.get("build_number"),
                "branch": doc.get("branch", ""),
                "event": raw_data.get("event", ""),
                "workflow_name": raw_data.get("name", ""),
            }

        return result

    def find_with_filters(
        self,
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None,
        languages: Optional[List[str]] = None,
        conclusions: Optional[List[str]] = None,
        ci_provider: Optional[str] = None,
        exclude_bots: bool = True,
        repo_ids: Optional[List[ObjectId]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[RawBuildRun], Dict[str, Any]]:
        """
        Find build runs with filters and return stats for preview.

        Used by Training Scenario wizard to preview matching builds.

        Returns:
            Tuple of (builds list, stats dict with total_builds, total_repos, outcome_distribution)
        """
        query: Dict[str, Any] = {}

        # Date range filter
        if date_start or date_end:
            query["run_started_at"] = {}
            if date_start:
                query["run_started_at"]["$gte"] = date_start
            if date_end:
                query["run_started_at"]["$lte"] = date_end

        # Conclusion filter
        if conclusions:
            query["conclusion"] = {"$in": conclusions}

        # CI provider filter
        if ci_provider and ci_provider != "all":
            query["provider"] = ci_provider

        # Exclude bot commits
        if exclude_bots:
            query["is_bot_commit"] = {"$ne": True}

        # Repo IDs filter (for language filtering - requires join with raw_repositories)
        if repo_ids:
            query["raw_repo_id"] = {"$in": repo_ids}

        # Get paginated builds
        builds, total = self.paginate(
            query,
            sort=[("run_created_at", -1)],
            skip=skip,
            limit=limit,
        )

        # Get stats via aggregation
        stats_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "total_builds": {"$sum": 1},
                    "unique_repos": {"$addToSet": "$raw_repo_id"},
                    "success_count": {
                        "$sum": {"$cond": [{"$eq": ["$conclusion", "success"]}, 1, 0]}
                    },
                    "failure_count": {
                        "$sum": {"$cond": [{"$eq": ["$conclusion", "failure"]}, 1, 0]}
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_builds": 1,
                    "total_repos": {"$size": "$unique_repos"},
                    "outcome_distribution": {
                        "success": "$success_count",
                        "failure": "$failure_count",
                    },
                }
            },
        ]

        stats_result = list(self.collection.aggregate(stats_pipeline))
        stats = (
            stats_result[0]
            if stats_result
            else {
                "total_builds": 0,
                "total_repos": 0,
                "outcome_distribution": {"success": 0, "failure": 0},
            }
        )

        return builds, stats

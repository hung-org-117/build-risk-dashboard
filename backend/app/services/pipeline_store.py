"""MongoDB persistence helpers for the ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(job: Dict[str, Any]) -> Dict[str, Any]:
    if not job:
        return {}
    payload = job.copy()
    identifier = payload.pop("_id", None)
    if identifier is not None:
        payload["id"] = str(identifier)
    # Convert any Mongo ObjectId fields (e.g., user_id) to strings for JSON
    if payload.get("user_id") is not None:
        try:
            from bson import ObjectId

            if isinstance(payload["user_id"], ObjectId):
                payload["user_id"] = str(payload["user_id"])
        except Exception:
            # leave as-is if conversion is not applicable
            pass
    for key, value in payload.items():
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


class PipelineStore:
    """Facade responsible for persisting pipeline entities."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_repository(
        self,
        *,
        user_id: Optional[str],
        provider: str,
        full_name: str,
        default_branch: str,
        is_private: bool,
        main_lang: Optional[str],
        github_repo_id: Optional[int],
        metadata: Dict[str, Any],
        last_scanned_at: Optional[datetime] = None,
        installation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utcnow()
        existing = self.db.repositories.find_one(
            {"provider": provider, "full_name": full_name}
        )
        try:
            if isinstance(user_id, str):
                converted = ObjectId(user_id)
                owner_id = converted
            else:
                owner_id = user_id
        except Exception:
            owner_id = user_id

        document = {
            "user_id": owner_id,
            "provider": provider,
            "full_name": full_name,
            "default_branch": default_branch,
            "is_private": is_private,
            "main_lang": main_lang,
            "github_repo_id": github_repo_id,
            "metadata": metadata,
            "updated_at": now,
        }
        document["ci_provider"] = (existing or {}).get("ci_provider", "github_actions")
        document["monitoring_enabled"] = (existing or {}).get(
            "monitoring_enabled", True
        )
        document["sync_status"] = (existing or {}).get("sync_status", "healthy")
        document["webhook_status"] = (existing or {}).get("webhook_status", "inactive")
        document["ci_token_status"] = (existing or {}).get("ci_token_status", "valid")
        tracked = (existing or {}).get("tracked_branches")
        if not tracked:
            tracked = [default_branch] if default_branch else []
        document["tracked_branches"] = tracked
        document["last_sync_error"] = (existing or {}).get("last_sync_error")
        document["notes"] = (existing or {}).get("notes")
        if installation_id is not None:
            document["installation_id"] = installation_id
        elif existing:
            document["installation_id"] = existing.get("installation_id")
        if last_scanned_at is not None:
            document["last_scanned_at"] = last_scanned_at
        elif existing:
            document["last_scanned_at"] = existing.get("last_scanned_at")
        else:
            document["last_scanned_at"] = None
        if existing:
            repo_id = existing["_id"]
            self.db.repositories.update_one(
                {"_id": repo_id},
                {"$set": document},
            )
            return self.db.repositories.find_one({"_id": repo_id})
        else:
            document["created_at"] = now
            insert_result = self.db.repositories.insert_one(document)
            document["_id"] = insert_result.inserted_id
            return document

    def update_repository(
        self, repo_id: str | ObjectId, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        identifier = repo_id
        if isinstance(repo_id, str):
            try:
                identifier = ObjectId(repo_id)
            except (InvalidId, TypeError):
                return None
        payload = updates.copy()
        if "tracked_branches" in payload and payload["tracked_branches"] is None:
            payload["tracked_branches"] = []
        payload["updated_at"] = _utcnow()
        self.db.repositories.update_one({"_id": identifier}, {"$set": payload})
        return self.db.repositories.find_one({"_id": identifier})

    def list_repositories(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if user_id is not None:
            # Convert string looking like an ObjectId to the ObjectId type so it
            # matches stored ObjectId references.
            if isinstance(user_id, str):
                try:
                    from bson import ObjectId

                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    # not an ObjectId string — try to coerce to int if numeric
                    if user_id.isdigit():
                        query["user_id"] = int(user_id)
                    else:
                        query["user_id"] = user_id
            else:
                query["user_id"] = user_id
        cursor = self.db.repositories.find(query).sort("created_at", -1)
        return list(cursor)

    def count_builds_by_repository(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        pipeline = [
            {"$group": {"_id": "$repository", "count": {"$sum": 1}}},
        ]
        for doc in self.db.builds.aggregate(pipeline):
            repo_name = doc.get("_id")
            if repo_name:
                counts[repo_name] = doc.get("count", 0)
        return counts

    def count_builds_for_repo(self, repository: str) -> int:
        if not repository:
            return 0
        return self.db.builds.count_documents({"repository": repository})

    def list_repo_jobs(self, repository: str, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = (
            self.db.github_import_jobs.find({"repository": repository})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [_serialize(job) for job in cursor]

    def get_repository(self, repo_id: str | ObjectId) -> Optional[Dict[str, Any]]:
        identifier = repo_id
        if isinstance(repo_id, str):
            try:
                identifier = ObjectId(repo_id)
            except (InvalidId, TypeError):
                return None
        return self.db.repositories.find_one({"_id": identifier})

    # --- Workflow runs ----------------------------------------------------
    def upsert_workflow_run(
        self, run_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        doc = payload.copy()
        doc["updated_at"] = _utcnow()
        self.db.workflow_runs.update_one(
            {"_id": run_id},
            {
                "$set": doc,
                "$setOnInsert": {
                    "_id": run_id,
                    "created_at": _utcnow(),
                },
            },
            upsert=True,
        )
        return self.db.workflow_runs.find_one({"_id": run_id})

    def record_workflow_jobs(self, run_id: int, jobs: List[Dict[str, Any]]) -> None:
        for job in jobs:
            job_id = job.get("id")
            if job_id is None:
                continue
            document = job.copy()
            for key in ["started_at", "completed_at"]:
                value = document.get(key)
                if isinstance(value, str):
                    try:
                        document[key] = datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        )
                    except ValueError:  # pragma: no cover - GitHub values are ISO
                        pass
            document.update({"run_id": run_id, "updated_at": _utcnow()})
            self.db.workflow_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": document,
                    "$setOnInsert": {"created_at": _utcnow()},
                },
                upsert=True,
            )

    # --- Build records ----------------------------------------------------
    def upsert_build(self, build_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = data.copy()
        payload.update({"updated_at": _utcnow()})
        self.db.builds.update_one(
            {"_id": build_id},
            {
                "$set": payload,
                "$setOnInsert": {
                    "_id": build_id,
                    "created_at": _utcnow(),
                },
            },
            upsert=True,
        )
        return self.db.builds.find_one({"_id": build_id})

    def append_build_commits(
        self, build_id: int, commits: List[Dict[str, Any]]
    ) -> None:
        if not commits:
            return
        self.update_build_features(
            build_id,
            git_all_built_commits=commits,
            git_num_all_built_commits=len(commits),
        )

    def record_build_feature_block(
        self, build_id: int, block: str, data: Dict[str, Any]
    ) -> None:
        prefixed = {f"features.{block}.{key}": value for key, value in data.items()}
        prefixed["updated_at"] = _utcnow()
        self.db.builds.update_one({"_id": build_id}, {"$set": prefixed})

    def update_build_features(self, build_id: int, **features: Any) -> None:
        if not features:
            return
        update = {f"features.{key}": value for key, value in features.items()}
        update["updated_at"] = _utcnow()
        self.db.builds.update_one({"_id": build_id}, {"$set": update})

    # --- Import job helpers -----------------------------------------------
    def create_import_job(
        self,
        repository: str,
        branch: str,
        initiated_by: str,
        user_id: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utcnow()
        doc = {
            "_id": uuid4().hex,
            "repository": repository,
            "branch": branch,
            "status": "pending",
            "progress": 0,
            "builds_imported": 0,
            "commits_analyzed": 0,
            "tests_collected": 0,
            "initiated_by": initiated_by,
            "user_id": user_id,
            "installation_id": installation_id,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "last_error": None,
            "notes": None,
        }
        self.db.github_import_jobs.insert_one(doc)
        return _serialize(doc)

    def update_import_job(self, job_id: str, **updates: Any) -> Dict[str, Any]:
        updates.setdefault("updated_at", _utcnow())
        self.db.github_import_jobs.update_one({"_id": job_id}, {"$set": updates})
        job = self.db.github_import_jobs.find_one({"_id": job_id})
        return _serialize(job) if job else {}

    def list_import_jobs(self) -> List[Dict[str, Any]]:
        jobs = self.db.github_import_jobs.find().sort("created_at", -1)
        return [_serialize(job) for job in jobs]

    # --- Workflow cursors -------------------------------------------------
    def get_workflow_cursor(
        self, repository: str, branch: str
    ) -> Optional[Dict[str, Any]]:
        return self.db.workflow_cursors.find_one(
            {"repository": repository, "branch": branch}
        )

    def update_workflow_cursor(
        self, repository: str, branch: str, run_id: int, started_at: datetime
    ) -> None:
        document = {
            "repository": repository,
            "branch": branch,
            "last_run_id": run_id,
            "last_run_started_at": started_at,
            "updated_at": _utcnow(),
        }
        self.db.workflow_cursors.update_one(
            {"repository": repository, "branch": branch},
            {
                "$set": document,
                "$setOnInsert": {"created_at": _utcnow()},
            },
            upsert=True,
        )

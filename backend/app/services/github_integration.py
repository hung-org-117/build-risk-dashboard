"""GitHub integration status helpers backed by MongoDB."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from random import Random
from typing import Dict, List

from pymongo.database import Database

from app.config import settings

_rng = Random(2024)


def _aggregate_repo_stats(builds: List[dict]) -> List[dict]:
    repo_map: Dict[str, Dict[str, object]] = {}
    for build in builds:
        repository = build.get("repository", "unknown")
        repo_stats = repo_map.setdefault(
            repository,
            {
                "name": repository,
                "buildCount": 0,
                "highRiskCount": 0,
                "status": "healthy",
                "lastSync": build.get("updated_at") or build.get("created_at"),
            },
        )
        repo_stats["buildCount"] += 1
        risk_assessment = build.get("risk_assessment") or {}
        risk_level = risk_assessment.get("risk_level", "low")
        if risk_level in {"high", "critical"}:
            repo_stats["highRiskCount"] += 1
            repo_stats["status"] = "attention"
        elif risk_level == "medium" and repo_stats.get("status") != "attention":
            repo_stats["status"] = "degraded"

        candidate_date = build.get("updated_at") or build.get("created_at")
        last_sync = repo_stats.get("lastSync")
        if candidate_date and (last_sync is None or candidate_date > last_sync):
            repo_stats["lastSync"] = candidate_date

    results = []
    for stats in repo_map.values():
        last_sync = stats.get("lastSync")
        if isinstance(last_sync, str):
            stats["lastSync"] = last_sync
        elif hasattr(last_sync, "isoformat"):
            stats["lastSync"] = last_sync.isoformat()
        else:
            stats["lastSync"] = None
        results.append(stats)
    return results


def get_github_status(db: Database) -> Dict[str, object]:
    connection = db.github_connection.find_one({})
    scopes = settings.GITHUB_SCOPES or ["read:user", "repo", "read:org", "workflow"]

    if not connection:
        return {
            "connected": False,
            "organization": None,
            "connectedAt": None,
            "scopes": scopes,
            "repositories": [],
            "lastSyncStatus": "warning",
            "lastSyncMessage": "Chưa ủy quyền GitHub OAuth.",
            "accountLogin": None,
            "accountName": None,
            "accountAvatarUrl": None,
        }

    builds = list(db.builds.find())
    repositories = _aggregate_repo_stats(builds)

    status = connection.get("last_sync_status", "warning")
    message = connection.get("last_sync_message", "Chưa chạy collector kể từ khi ủy quyền.")

    connected_at = connection.get("connected_at")
    if hasattr(connected_at, "isoformat"):
        connected_at = connected_at.isoformat()

    return {
        "connected": True,
        "organization": connection.get("organization") or connection.get("account_login"),
        "connectedAt": connected_at,
        "scopes": scopes,
        "repositories": repositories,
        "lastSyncStatus": status,
        "lastSyncMessage": message,
        "accountLogin": connection.get("account_login"),
        "accountName": connection.get("account_name"),
        "accountAvatarUrl": connection.get("account_avatar_url"),
    }


def _serialize_import_job(document: Dict[str, object]) -> Dict[str, object]:
    job = document.copy()
    job["id"] = str(job.pop("_id"))
    for key in ["created_at", "started_at", "completed_at"]:
        value = job.get(key)
        if isinstance(value, datetime):
            job[key] = value.isoformat()
    return job


def list_import_jobs(db: Database) -> List[Dict[str, object]]:
    jobs = db.github_import_jobs.find().sort("created_at", -1)
    return [_serialize_import_job(job) for job in jobs]


def create_import_job(db: Database, repository: str, branch: str, initiated_by: str = "admin") -> Dict[str, object]:
    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4().hex[:10]
    progress = _rng.randint(25, 80)
    builds_imported = int(progress * 1.6)
    commits_analyzed = builds_imported * 5
    tests_collected = builds_imported * 2

    status = "running"
    started_at = now - timedelta(minutes=_rng.randint(3, 12))
    job_doc = {
        "_id": job_id,
        "repository": repository,
        "branch": branch,
        "status": status,
        "progress": progress,
        "builds_imported": builds_imported,
        "commits_analyzed": commits_analyzed,
        "tests_collected": tests_collected,
        "initiated_by": initiated_by,
        "created_at": now,
        "started_at": started_at,
        "completed_at": None,
        "last_error": None,
        "notes": "Đồng bộ lịch sử workflow runs + artifacts",
    }

    db.github_import_jobs.insert_one(job_doc)
    return _serialize_import_job(job_doc)

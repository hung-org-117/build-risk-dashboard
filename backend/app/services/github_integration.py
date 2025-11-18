"""GitHub integration status helpers backed by MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from pymongo.database import Database

from app.config import settings
from app.services.pipeline_store import PipelineStore
from app.tasks.repositories import enqueue_repo_import


def _aggregate_repo_stats(builds: List[dict]) -> List[dict]:
    repo_map: Dict[str, Dict[str, object]] = {}
    for build in builds:
        repository = build.get("repository", "unknown")
        repo_stats = repo_map.setdefault(
            repository,
            {
                "name": repository,
                "buildCount": 0,
                "status": "healthy",
                "lastSync": build.get("updated_at") or build.get("created_at"),
            },
        )
        repo_stats["buildCount"] += 1

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
    # Use oauth_identities to determine whether any GitHub identity exists.
    connection = db.oauth_identities.find_one({"provider": "github"})
    scopes = settings.GITHUB_SCOPES

    if not connection or not connection.get("access_token"):
        return {
            "connected": False,
            "organization": None,
            "connectedAt": None,
            "scopes": scopes,
            "repositories": [],
            "lastSyncStatus": "warning",
            "lastSyncMessage": "GitHub OAuth not authorized.",
            "accountLogin": None,
            "accountName": None,
            "accountAvatarUrl": None,
        }

    builds = list(db.builds.find())
    repositories = _aggregate_repo_stats(builds)

    # `last_sync_status` and `last_sync_message` were previously stored on a
    # global github_connection document. Keep fallbacks when migrating away.
    status = connection.get("last_sync_status", "warning") if connection else "warning"
    message = (
        connection.get(
            "last_sync_message", "Collector has not run since authorization."
        )
        if connection
        else "GitHub OAuth not authorized."
    )

    connected_at = connection.get("connected_at")
    if hasattr(connected_at, "isoformat"):
        connected_at = connected_at.isoformat()

    return {
        "connected": True,
        "organization": (
            (connection.get("organization") or connection.get("account_login"))
            if connection
            else None
        ),
        "connectedAt": connected_at,
        "scopes": scopes,
        "repositories": repositories,
        "lastSyncStatus": status,
        "lastSyncMessage": message,
        "accountLogin": connection.get("account_login") if connection else None,
        "accountName": connection.get("account_name") if connection else None,
        "accountAvatarUrl": (
            connection.get("account_avatar_url") if connection else None
        ),
    }


def list_import_jobs(db: Database) -> List[Dict[str, object]]:
    store = PipelineStore(db)
    return store.list_import_jobs()


def create_import_job(
    db: Database,
    repository: str,
    branch: str,
    initiated_by: str = "admin",
    user_id: str | None = None,
    installation_id: str | None = None,
) -> Dict[str, object]:
    store = PipelineStore(db)
    job = store.create_import_job(
        repository,
        branch,
        initiated_by,
        user_id=user_id,
        installation_id=installation_id,
    )
    job_id = job.get("id")
    start_time = datetime.now(timezone.utc)

    store.update_import_job(
        job_id,
        status="queued",
        progress=1,
        started_at=start_time,
        notes="Collecting repository metadata",
    )
    enqueue_repo_import.delay(repository, branch, job_id, user_id, installation_id)
    return store.update_import_job(
        job_id,
        status="waiting_webhook",
        notes="Metadata collected. Configure the GitHub webhook to receive workflow events.",
    )

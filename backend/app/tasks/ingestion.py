"""Ingestion tasks for repository backfill"""

from app.repositories.imported_repository import ImportedRepositoryRepository
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from app.celery_app import celery_app
from app.services.github.github_client import get_app_github_client
from app.repositories.scan_job import ScanJobRepository
from app.tasks.base import PipelineTask
from app.services.github.exceptions import GithubRateLimitError

logger = logging.getLogger(__name__)

import os
from pathlib import Path

LOG_DIR = Path("job_logs")
LOG_DIR.mkdir(exist_ok=True)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ingestion.import_repo",
    queue="import_repo",
)
def import_repo(
    self: PipelineTask,
    user_id: str,
    full_name: str,
    installation_id: str,
    provider: str = "github",
    test_frameworks: list[str] | None = None,
    source_languages: list[str] | None = None,
    ci_provider: str = "github_actions",
) -> Dict[str, Any]:
    """
    Import and scan a repository.
    1. Fetch metadata from GitHub
    2. Upsert repository record
    3. Mark as imported in available_repos
    4. Trigger initial scan (list workflows)
    """
    imported_repo_repo = ImportedRepositoryRepository(self.db)
    # 1. Fetch metadata
    try:
        with get_app_github_client(self.db, installation_id) as gh:
            repo_data = gh.get_repository(full_name)

            # 2. Upsert repository
            repo_doc = imported_repo_repo.upsert_repository(
                user_id=user_id,
                provider=provider,
                full_name=full_name,
                default_branch=repo_data.get("default_branch", "main"),
                is_private=bool(repo_data.get("private")),
                main_lang=repo_data.get("language"),
                github_repo_id=repo_data.get("id"),
                metadata=repo_data,
                installation_id=installation_id,
                last_scanned_at=None,
                test_frameworks=test_frameworks or [],
                source_languages=source_languages or [],
                ci_provider=ci_provider or "github_actions",
            )
            repo_id = str(repo_doc["_id"])

            # 3. Mark as imported
            from bson import ObjectId

            self.db.available_repositories.update_one(
                {"user_id": ObjectId(user_id), "full_name": full_name},
                {"$set": {"imported": True}},
            )

            # 4. Initial Scan Logic
            scan_repo = ScanJobRepository(self.db)
            job = scan_repo.get_active_job(repo_id)
            if not job:
                job = scan_repo.create_job(repo_id)

            job_id = str(job["_id"])
            scan_repo.update_progress(
                job_id, status="running", phase="discovering_builds"
            )

            runs = gh.list_workflow_runs(full_name, params={"per_page": 100})
            scan_repo.update_progress(job_id, total_runs=len(runs))

            for run in runs:
                process_workflow_run.delay(repo_id, run)

            scan_repo.update_progress(job_id, status="completed", phase="finalizing")

    except GithubRateLimitError as e:
        wait = e.retry_after if e.retry_after else 60
        logger.warning("Rate limit hit in import_repo. Retrying in %s seconds.", wait)
        raise self.retry(exc=e, countdown=wait)
    except Exception as e:
        logger.error(f"Failed to import repo {full_name}: {e}")
        # If we have a job_id, mark it failed
        if "job_id" in locals():
            scan_repo.update_progress(job_id, status="failed", error=str(e))
        raise e

    return {
        "status": "completed",
        "repo_id": repo_id,
        "runs_found": len(runs) if "runs" in locals() else 0,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ingestion.process_workflow_run",
    queue="collect_workflow_logs",
)
def process_workflow_run(
    self: PipelineTask, repo_id: str, run: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a single workflow run:
    1. Fetch workflow jobs
    2. Download logs for each job
    3. (Future) Parse logs and create BuildSnapshot
    """
    repo_repo = ImportedRepositoryRepository(self.db)
    repo = repo_repo.find_by_id(repo_id)
    if not repo:
        return {"status": "error", "message": "Repository not found"}

    full_name = repo.get("full_name")
    installation_id = repo.get("installation_id")
    run_id = run.get("id")

    if not installation_id:
        raise ValueError(f"Repository {full_name} missing installation_id")

    try:
        with get_app_github_client(self.db, installation_id) as gh:
            # 1. Fetch workflow jobs
            jobs = gh.list_workflow_jobs(full_name, run_id)

            logs_collected = 0
            for job in jobs:
                job_id = job.get("id")
                # 2. Download logs for each job
                try:
                    # Check if logs are available first to avoid 404s or wasted bandwidth
                    # But download_job_logs handles errors too.
                    log_content = gh.download_job_logs(full_name, job_id)
                    if log_content:
                        logs_collected += 1
                        # Save log to file
                        log_path = LOG_DIR / str(repo_id) / str(run_id)
                        log_path.mkdir(parents=True, exist_ok=True)
                        file_path = log_path / f"{job_id}.log"
                        with open(file_path, "wb") as f:
                            f.write(log_content)
                except Exception as e:
                    logger.error(
                        "Failed to download logs for job %s in run %s (repo: %s): %s",
                        job_id,
                        run_id,
                        full_name,
                        str(e),
                        exc_info=True,
                    )
    except GithubRateLimitError as e:
        wait = e.retry_after if e.retry_after else 60
        logger.warning(
            "Rate limit hit in process_workflow_run. Retrying in %s seconds.", wait
        )
        raise self.retry(exc=e, countdown=wait)

    return {
        "repo_id": repo_id,
        "run_id": run_id,
        "jobs_processed": len(jobs),
        "logs_collected": logs_collected,
    }

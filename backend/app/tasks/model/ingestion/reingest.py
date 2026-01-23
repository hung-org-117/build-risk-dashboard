"""
Model Ingestion Reingest Tasks.

Tasks for retrying failed builds and webhook ingestion:
- reingest_failed_builds: Retry FAILED import builds
- ingest_webhook_build: Ingest a single build from webhook event
"""

import logging
import uuid
from typing import Any, Dict

from bson import ObjectId

from app.celery_app import celery_app
from app.ci_providers import CIProvider
from app.entities.model_import_build import ModelImportBuild, ModelImportBuildStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_import_build import ModelImportBuildRepository
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.model.ingestion.common import create_repo_config_failure_handler
from app.tasks.model.ingestion.dispatch import dispatch_ingestion
from app.tasks.model_processing import publish_status

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_ingestion.reingest_failed_builds",
    queue="model_ingestion",
    soft_time_limit=600,
    time_limit=900,
)
def reingest_failed_builds(
    self: SafeTask,
    repo_config_id: str,
) -> Dict[str, Any]:
    """
    Retry FAILED import builds (actual errors only).

    Only retries builds with status=FAILED (actual errors like timeout, network failure).
    Does NOT retry MISSING_RESOURCE builds (expected - logs expired, commit not found).
    """

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        import_build_repo = ModelImportBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            logger.error(f"Repo config not found: {repo_config_id}")
            return {"status": "error", "message": "Repo config not found"}

        checkpoint_id = repo_config.last_processed_import_build_id
        failed_builds = import_build_repo.find_failed_builds(repo_config_id, after_id=checkpoint_id)

        if not failed_builds:
            missing_count = import_build_repo.count_missing_resource_after_checkpoint(
                repo_config_id, checkpoint_id
            )
            msg = "No failed builds to retry"
            if missing_count > 0:
                msg += f" ({missing_count} builds have missing resources - not retryable)"
            logger.info(f"{msg} for {repo_config_id}")
            return {
                "status": "no_failed_builds",
                "failed_count": 0,
                "missing_resource_count": missing_count,
                "checkpoint": str(checkpoint_id) if checkpoint_id else None,
            }

        correlation_id = str(uuid.uuid4())[:8]
        logger.info(
            f"[corr={correlation_id}] Found {len(failed_builds)} failed builds "
            f"after checkpoint {checkpoint_id} for {repo_config_id}"
        )

        commit_shas = []
        ci_run_ids = []

        reset_count = 0
        for import_build in failed_builds:
            try:
                import_build_repo.update_one(
                    str(import_build.id),
                    {
                        "status": ModelImportBuildStatus.FETCHED.value,
                        "ingestion_error": None,
                        "ingested_at": None,
                    },
                )
                reset_count += 1

                if import_build.commit_sha:
                    commit_shas.append(import_build.commit_sha)
                ci_run_ids.append(import_build.ci_run_id)

            except Exception as e:
                logger.warning(f"Failed to reset import build {import_build.id}: {e}")

        if not ci_run_ids:
            logger.warning(f"No CI run IDs to reingest for {repo_config_id}")
            return {"status": "no_runs_to_reingest", "count": 0}

        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.INGESTING.value},
        )

        raw_repo = RawRepositoryRepository(self.db).find_by_id(str(repo_config.raw_repo_id))
        if not raw_repo:
            logger.error(f"Raw repo not found: {repo_config.raw_repo_id}")
            return {"status": "error", "message": "Raw repo not found"}

        dispatch_ingestion.delay(
            repo_config_id=repo_config_id,
            raw_repo_id=str(repo_config.raw_repo_id),
            github_repo_id=raw_repo.github_repo_id,
            full_name=raw_repo.full_name,
            ci_provider=repo_config.ci_provider or CIProvider.GITHUB_ACTIONS.value,
            commit_shas=commit_shas,
            ci_run_ids=ci_run_ids,
            correlation_id=correlation_id,
        )

        publish_status(
            repo_config_id,
            "ingesting",
            f"Retrying {reset_count} failed imports...",
        )

        return {
            "status": "queued",
            "imports_reset": reset_count,
            "total_failed": len(failed_builds),
            "correlation_id": correlation_id,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_ingestion.ingest_webhook_build",
    queue="model_ingestion",
    soft_time_limit=300,
    time_limit=360,
)
def ingest_webhook_build(
    self: SafeTask,
    repo_config_id: str,
    raw_repo_id: str,
    raw_build_run_id: str,
    full_name: str,
    ci_provider: str,
    commit_sha: str,
    ci_run_id: str,
    github_repo_id: int,
) -> Dict[str, Any]:
    """
    Ingest a single build from webhook event.

    This task is triggered by GitHub webhook when a workflow_run completes.
    It only runs ingestion (clone, worktree, logs) - does NOT auto-process.
    """
    correlation_id = str(uuid.uuid4())[:8]
    corr_prefix = f"[corr={correlation_id}][webhook]"

    logger.info(
        f"{corr_prefix} Starting webhook ingestion for build {ci_run_id} " f"in repo {full_name}"
    )

    import_build_repo = ModelImportBuildRepository(self.db)
    repo_config_repo = ModelRepoConfigRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    repo_config = repo_config_repo.find_by_id(repo_config_id)
    if not repo_config:
        logger.error(f"{corr_prefix} ModelRepoConfig not found: {repo_config_id}")
        return {"status": "error", "error": "ModelRepoConfig not found"}

    raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
    if not raw_repo:
        logger.error(f"{corr_prefix} RawRepository not found: {raw_repo_id}")
        return {"status": "error", "error": "RawRepository not found"}

    github_repo_id = github_repo_id or raw_repo.github_repo_id

    existing_import = import_build_repo.find_by_business_key(repo_config_id, raw_build_run_id)

    if existing_import:
        logger.info(f"{corr_prefix} Build {ci_run_id} already ingested, skipping")
        return {"status": "already_ingested", "build_id": ci_run_id}

    raw_build_run = RawBuildRunRepository(self.db).find_by_id(raw_build_run_id)
    run_created_at = raw_build_run.run_created_at if raw_build_run else None

    import_build = ModelImportBuild(
        _id=None,
        model_repo_config_id=ObjectId(repo_config_id),
        raw_build_run_id=ObjectId(raw_build_run_id),
        status=ModelImportBuildStatus.FETCHED,
        ci_run_id=ci_run_id,
        commit_sha=commit_sha,
        run_created_at=run_created_at,
        ingestion_started_at=None,
        ingested_at=None,
        ingestion_error=None,
    )
    result = import_build_repo.insert_one(import_build)
    import_build_id = str(result.id)
    logger.info(f"{corr_prefix} Created ModelImportBuild {import_build_id}")

    dispatch_ingestion.delay(
        repo_config_id=repo_config_id,
        raw_repo_id=raw_repo_id,
        github_repo_id=github_repo_id,
        full_name=full_name,
        ci_provider=ci_provider,
        commit_shas=[commit_sha],
        ci_run_ids=[ci_run_id],
        correlation_id=correlation_id,
    )

    publish_status(
        repo_config_id,
        "ingesting",
        f"Ingesting new build from webhook: {ci_run_id[:8]}...",
        stats={
            "builds_fetched": 1,
            "builds_features_extracted": 0,
            "builds_missing_resource": 0,
        },
    )

    logger.info(f"{corr_prefix} Dispatched ingestion for webhook build {ci_run_id}")

    return {
        "status": "dispatched",
        "build_id": ci_run_id,
        "import_build_id": import_build_id,
        "correlation_id": correlation_id,
    }

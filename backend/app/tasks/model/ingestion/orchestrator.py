"""
Model Ingestion Orchestrator Tasks.

Entry point tasks for model ingestion pipeline:
- start_model_processing: Main entry point
- ingest_model_builds: Dispatch fetch tasks
"""

import logging
import uuid
from typing import Any, Dict, Optional

from celery import chord, group

from app.celery_app import celery_app
from app.config import settings
from app.core.tracing import TracingContext
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.model.ingestion.common import create_repo_config_failure_handler
from app.tasks.model_processing import publish_status

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_ingestion.start_model_processing",
    queue="model_processing",
    soft_time_limit=120,
    time_limit=180,
)
def start_model_processing(
    self: SafeTask,
    repo_config_id: str,
    ci_provider: str,
    max_builds: Optional[int] = None,
    since_days: Optional[int] = None,
    sync_until_existing: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrator: Start ingestion for repo, then dispatch processing.

    Flow: start_model_processing -> ingest_model_builds -> dispatch_build_processing
    """

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        # Generate correlation_id for tracing entire flow
        correlation_id = str(uuid.uuid4())

        # Set tracing context for structured logging
        TracingContext.set(
            correlation_id=correlation_id,
            repo_id=repo_config_id,
            pipeline_type="model_processing",
        )

        model_repo_config_repo = ModelRepoConfigRepository(self.db)

        # Validate repo exists
        repo = model_repo_config_repo.find_by_id(repo_config_id)
        if not repo:
            logger.error(f"Repository {repo_config_id} not found")
            return {"status": "error", "error": "Repository not found"}

        # Mark as started
        model_repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.INGESTING.value},
        )
        publish_status(repo_config_id, "ingesting", "Starting import workflow...")

        ingest_model_builds.delay(
            repo_config_id=repo_config_id,
            ci_provider=ci_provider,
            max_builds=max_builds,
            since_days=since_days,
            sync_until_existing=sync_until_existing,
            correlation_id=correlation_id,
        )

        logger.info(f"Dispatched model processing workflow for {repo.full_name}")

        return {
            "status": "dispatched",
            "repo_config_id": repo_config_id,
            "full_name": repo.full_name,
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
    name="app.tasks.model_ingestion.ingest_model_builds",
    queue="model_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def ingest_model_builds(
    self: SafeTask,
    repo_config_id: str,
    ci_provider: str,
    max_builds: Optional[int] = None,
    since_days: Optional[int] = None,
    batch_size: Optional[int] = None,
    sync_until_existing: bool = False,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Orchestrator: Dispatch fetch batch tasks as chord.

    Args:
        repo_config_id: The model repo config ID
        ci_provider: CI provider to use (e.g., "github_actions")
        max_builds: Maximum number of builds to fetch (ignored if sync_until_existing=True)
        since_days: Only fetch builds from the last N days (ignored if sync_until_existing=True)
        batch_size: Number of builds per page
        sync_until_existing: If True, fetch sequentially until hitting existing builds
        correlation_id: Optional correlation ID for tracing (generates new if not provided)

    Flow:
        ingest_model_builds
            └── chord(
                    group(fetch_builds_batch tasks per page),
                    aggregate_fetch_results
                )
    """
    # Import here to avoid circular imports
    from app.tasks.model.ingestion.fetch import (
        aggregate_fetch_results,
        fetch_builds_batch,
        fetch_builds_until_existing,
        handle_fetch_chord_error,
    )

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        nonlocal correlation_id
        # Use provided correlation_id or generate new one
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        corr_prefix = f"[corr={correlation_id[:8]}]"

        effective_batch_size = batch_size or settings.INGESTION_BUILDS_PER_PAGE

        # Set tracing context
        TracingContext.set(
            correlation_id=correlation_id,
            repo_id=repo_config_id,
            pipeline_type="model_ingestion",
        )

        repo_config_repo = ModelRepoConfigRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            raise ValueError(f"ModelRepoConfig {repo_config_id} not found")

        logger.info(f"{corr_prefix}[model_ingestion] Starting for {repo_config.full_name}")

        # Update repo_config status
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.FETCHING.value,
            },
        )

        publish_status(repo_config_id, "fetching", "Fetching builds from CI...")

        # Route to appropriate fetch strategy
        if sync_until_existing:
            # Sequential fetch that stops when hitting existing builds
            logger.info(f"{corr_prefix} Using sync_until_existing mode")
            fetch_builds_until_existing.delay(
                repo_config_id=repo_config_id,
                ci_provider=ci_provider,
                batch_size=effective_batch_size,
                correlation_id=correlation_id,
            )
            return {
                "status": "dispatched",
                "repo_config_id": repo_config_id,
                "correlation_id": correlation_id,
                "mode": "sync_until_existing",
            }

        # Original parallel fetch mode
        estimated_pages = (max_builds // effective_batch_size + 1) if max_builds else 10

        # Build fetch tasks for each page
        fetch_tasks = []
        remaining = max_builds
        for page in range(1, estimated_pages + 1):
            api_limit = min(effective_batch_size, remaining) if remaining else effective_batch_size
            fetch_tasks.append(
                fetch_builds_batch.si(
                    repo_config_id=repo_config_id,
                    ci_provider=ci_provider,
                    page=page,
                    batch_size=api_limit,
                    since_days=since_days,
                    correlation_id=correlation_id,
                )
            )
            if remaining:
                remaining = max(0, remaining - api_limit)
                if remaining == 0:
                    break

        # Dispatch chord: fetch all pages → aggregate results
        callback = aggregate_fetch_results.s(
            repo_config_id=repo_config_id,
            correlation_id=correlation_id,
        ).on_error(
            handle_fetch_chord_error.s(
                repo_config_id=repo_config_id,
                correlation_id=correlation_id,
            )
        )

        workflow = chord(group(fetch_tasks), callback)
        workflow.apply_async()

        logger.info(f"{corr_prefix} Dispatched {len(fetch_tasks)} fetch tasks")

        return {
            "status": "dispatched",
            "repo_config_id": repo_config_id,
            "correlation_id": correlation_id,
            "fetch_tasks": len(fetch_tasks),
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )

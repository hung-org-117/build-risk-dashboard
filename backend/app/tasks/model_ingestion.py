"""
Model Ingestion Tasks - Resource preparation for model training builds.

This module uses chain-based task pattern for fetching builds:
1. ingest_model_builds - Orchestrator: Dispatches first batch
2. fetch_builds_batch - Fetches one page, saves to DB, chains to next page
3. prepare_and_dispatch_processing - Prepares resources and dispatches processing

Flow:
  ingest_model_builds → fetch_builds_batch(page=1) → fetch_builds_batch(page=2) → ... → prepare_and_dispatch_processing
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.celery_app import celery_app
from app.ci_providers import CIProvider, get_ci_provider, get_provider_config
from app.ci_providers.models import BuildStatus
from app.core.tracing import TracingContext
from app.entities.pipeline_run import PipelineRun, PipelineStatus, PipelineType
from app.repositories.dataset_template_repository import DatasetTemplateRepository
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.services.github.exceptions import GithubRateLimitError, GithubRetryableError
from app.tasks.base import PipelineTask
from app.tasks.model_processing import publish_status
from app.tasks.pipeline.feature_dag._metadata import get_required_resources_for_features
from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
from app.tasks.pipeline.shared.resources import FeatureResource
from app.tasks.shared import build_ingestion_workflow

logger = logging.getLogger(__name__)


def get_required_resources_for_template(db, template_name: str = "TravisTorrent Full") -> set:
    """Get required resources based on dataset template."""
    template_repo = DatasetTemplateRepository(db)
    template = template_repo.find_by_name(template_name)
    if template and template.feature_names:
        feature_set = set(template.feature_names)
        return get_required_resources_for_features(feature_set)
    return {r.value for r in FeatureResource}


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_ingestion.ingest_model_builds",
    queue="ingestion",
    soft_time_limit=60,
    time_limit=120,
)
def ingest_model_builds(
    self: PipelineTask,
    repo_config_id: str,
    ci_provider: str,
    max_builds: Optional[int] = None,
    since_days: Optional[int] = None,
    only_with_logs: bool = False,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Orchestrator: Dispatch first batch fetch task.

    This task validates the repo config and dispatches the first page fetch.
    Subsequent pages are fetched via chained tasks.
    """
    # Generate correlation_id for tracing entire flow
    correlation_id = str(uuid.uuid4())
    corr_prefix = f"[corr={correlation_id[:8]}]"

    # Use config batch size if not specified
    from app.config import settings

    batch_size = batch_size or settings.MODEL_FETCH_BATCH_SIZE

    # Set tracing context for structured logging
    TracingContext.set(
        correlation_id=correlation_id,
        repo_id=repo_config_id,
        pipeline_type=PipelineType.MODEL_INGESTION.value,
    )

    repo_config_repo = ModelRepoConfigRepository(self.db)
    pipeline_run_repo = PipelineRunRepository(self.db)
    repo_config = repo_config_repo.find_by_id(repo_config_id)

    if not repo_config:
        raise ValueError(f"ModelRepoConfig {repo_config_id} not found")

    # Create PipelineRun record for tracing
    pipeline_run = PipelineRun(
        correlation_id=correlation_id,
        pipeline_type=PipelineType.MODEL_INGESTION,
        repo_config_id=repo_config.id,
        triggered_by="system",
        request_id=self.request.id,
    )
    pipeline_run.start()
    pipeline_run_repo.insert_one(pipeline_run)

    logger.info(f"{corr_prefix}[model_ingestion] Starting ingestion for {repo_config.full_name}")

    # Dispatch first batch (page 1)
    fetch_builds_batch.delay(
        repo_config_id=repo_config_id,
        raw_repo_id=str(repo_config.raw_repo_id),
        full_name=repo_config.full_name,
        ci_provider=ci_provider,
        max_builds=max_builds,
        since_days=since_days,
        only_with_logs=only_with_logs,
        batch_size=batch_size,
        page=1,
        total_fetched=0,
        ci_build_ids=[],
        correlation_id=correlation_id,
    )

    return {
        "status": "dispatched",
        "repo_config_id": repo_config_id,
        "correlation_id": correlation_id,
        "message": "First batch fetch dispatched",
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_ingestion.fetch_builds_batch",
    queue="ingestion",
    soft_time_limit=300,
    time_limit=360,
    max_retries=5,  # Manual retry for rate limit errors
)
def fetch_builds_batch(
    self: PipelineTask,
    repo_config_id: str,
    raw_repo_id: str,
    full_name: str,
    ci_provider: str,
    page: int,
    total_fetched: int,
    ci_build_ids: List[str],
    max_builds: Optional[int] = None,
    since_days: Optional[int] = None,
    only_with_logs: bool = False,
    batch_size: Optional[int] = None,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Fetch a single page of builds, save to DB, and chain to next page or finalize.

    This task:
    1. Fetches one page from CI provider
    2. Saves builds to RawBuildRun collection
    3. Chains to next page OR prepare_and_dispatch_processing
    """
    import asyncio

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    log_ctx = f"{corr_prefix}[fetch_builds][page={page}][repo={full_name}]"

    build_run_repo = RawBuildRunRepository(self.db)

    since_dt = None
    if since_days:
        since_dt = datetime.now(timezone.utc) - timedelta(days=since_days)

    try:
        # Get CI provider instance
        ci_provider_enum = CIProvider(ci_provider)
        provider_config = get_provider_config(ci_provider_enum)
        ci_instance = get_ci_provider(ci_provider_enum, provider_config, db=self.db)

        fetch_kwargs = {
            "since": since_dt,
            "limit": batch_size,
            "page": page,
            "exclude_bots": True,
            "only_with_logs": only_with_logs,
            "only_completed": True,
        }

        # Fetch single page
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            builds = loop.run_until_complete(ci_instance.fetch_builds(full_name, **fetch_kwargs))
        finally:
            loop.close()

        # Process and save builds
        batch_ci_build_ids = []
        for build in builds:
            if build.status != BuildStatus.COMPLETED:
                continue

            raw_build_run = build_run_repo.upsert_by_business_key(
                raw_repo_id=ObjectId(raw_repo_id),
                build_id=build.build_id,
                provider=ci_provider_enum.value,
                build_number=build.build_number,
                repo_name=full_name,
                branch=build.branch or "",
                commit_sha=build.commit_sha,
                commit_message=None,
                commit_author=None,
                status=build.status,
                conclusion=build.conclusion,
                created_at=build.created_at or datetime.now(timezone.utc),
                started_at=None,
                completed_at=build.created_at or datetime.now(timezone.utc),
                duration_seconds=build.duration_seconds,
                web_url=build.web_url,
                logs_url=None,
                logs_available=build.logs_available or False,
                logs_path=None,
                raw_data=build.raw_data or {},
                is_bot_commit=build.is_bot_commit or False,
            )
            batch_ci_build_ids.append(raw_build_run.ci_run_id)

            # Check max builds limit
            if max_builds and (total_fetched + len(batch_ci_build_ids)) >= max_builds:
                break

        # Accumulate build IDs
        new_total = total_fetched + len(batch_ci_build_ids)
        new_ci_build_ids = ci_build_ids + batch_ci_build_ids

        logger.info(f"{log_ctx} Saved {len(batch_ci_build_ids)} builds (total: {new_total})")

        # Determine next action
        has_more = len(builds) >= batch_size
        reached_limit = max_builds and new_total >= max_builds

        if has_more and not reached_limit:
            # Chain to next page
            fetch_builds_batch.delay(
                repo_config_id=repo_config_id,
                raw_repo_id=raw_repo_id,
                full_name=full_name,
                ci_provider=ci_provider,
                page=page + 1,
                total_fetched=new_total,
                ci_build_ids=new_ci_build_ids,
                max_builds=max_builds,
                since_days=since_days,
                only_with_logs=only_with_logs,
                batch_size=batch_size,
                correlation_id=correlation_id,
            )
            return {
                "status": "chained",
                "page": page,
                "builds_this_page": len(batch_ci_build_ids),
                "total_so_far": new_total,
                "next_page": page + 1,
                "correlation_id": correlation_id,
            }
        else:
            prepare_and_dispatch_processing.delay(
                repo_config_id=repo_config_id,
                raw_repo_id=raw_repo_id,
                full_name=full_name,
                ci_provider=ci_provider,
                ci_build_ids=new_ci_build_ids,
                correlation_id=correlation_id,
            )
            return {
                "status": "completed",
                "page": page,
                "builds_this_page": len(batch_ci_build_ids),
                "total_builds": new_total,
                "correlation_id": correlation_id,
            }

    except (GithubRateLimitError, GithubRetryableError) as e:
        retries_left = self.max_retries - self.request.retries
        logger.warning(f"{log_ctx} Rate limit/retryable error (retries_left={retries_left}): {e}")
        if retries_left > 0:
            # Exponential backoff: 60s, 120s, 180s, etc.
            countdown = 60 * (self.request.retries + 1)
            raise self.retry(exc=e, countdown=countdown) from e
        else:
            # Max retries exhausted - mark as failed
            logger.error(f"{log_ctx} Max retries exhausted for rate limit")
            from app.entities.enums import ModelImportStatus

            repo_config_repo = ModelRepoConfigRepository(self.db)
            repo_config_repo.update_repository(
                repo_config_id,
                {
                    "import_status": ModelImportStatus.FAILED.value,
                    "last_sync_status": "failed",
                    "last_sync_error": f"Rate limit exhausted after {self.max_retries} retries",
                },
            )
            publish_status(repo_config_id, "failed", "Rate limit exhausted")
            raise
    except Exception as e:
        logger.error(f"{log_ctx} Failed: {e}")
        from app.entities.enums import ModelImportStatus

        repo_config_repo = ModelRepoConfigRepository(self.db)
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "import_status": ModelImportStatus.FAILED.value,
                "last_sync_status": "failed",
                "last_sync_error": str(e),
            },
        )
        publish_status(repo_config_id, "failed", str(e))
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_ingestion.prepare_and_dispatch_processing",
    queue="ingestion",
    soft_time_limit=300,
    time_limit=360,
)
def prepare_and_dispatch_processing(
    self: PipelineTask,
    repo_config_id: str,
    raw_repo_id: str,
    full_name: str,
    ci_provider: str,
    ci_build_ids: List[str],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Final step: Build ingestion workflow and dispatch processing.

    This task:
    1. Collects raw_build_run ObjectIds from ci_build_ids
    2. Gets commit SHAs for worktree creation
    3. Builds and applies ingestion workflow (clone, logs, worktrees)
    4. Dispatches dispatch_build_processing for feature extraction
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    log_ctx = f"{corr_prefix}[prepare_dispatch][repo={full_name}]"

    # Set tracing context for structured logging
    if correlation_id:
        TracingContext.set(
            correlation_id=correlation_id,
            repo_id=repo_config_id,
            pipeline_type=PipelineType.MODEL_INGESTION.value,
        )

    from app.tasks.model_processing import dispatch_build_processing

    pipeline_run_repo = PipelineRunRepository(self.db)

    if not ci_build_ids:
        logger.info(f"{log_ctx} No builds to process")
        from app.entities.enums import ModelImportStatus

        repo_config_repo = ModelRepoConfigRepository(self.db)
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "import_status": ModelImportStatus.IMPORTED.value,
                "last_sync_status": "success",
                "last_sync_error": None,
            },
        )
        publish_status(repo_config_id, "imported", "No builds found")

        # Complete PipelineRun with no builds
        if correlation_id:
            pipeline_run_repo.update_status(
                correlation_id=correlation_id,
                status=PipelineStatus.COMPLETED,
                result_summary={"builds_fetched": 0, "message": "No builds found"},
            )

        return {"status": "completed", "builds": 0, "message": "No builds found"}

    try:
        raw_build_run_repo = RawBuildRunRepository(self.db)
        ci_provider_enum = CIProvider(ci_provider)

        raw_build_docs = raw_build_run_repo.find_ids_by_build_ids(
            ObjectId(raw_repo_id), ci_build_ids, ci_provider_enum.value
        )

        raw_build_run_ids = [str(doc["_id"]) for doc in raw_build_docs]
        commit_shas = list(
            {
                doc.get("effective_sha") or doc.get("commit_sha")
                for doc in raw_build_docs
                if doc.get("commit_sha")
            }
        )

        logger.info(f"{log_ctx} Finalizing ingestion: {len(raw_build_run_ids)} builds")

        # Step 2: Determine required resources based on template
        required_resources = get_required_resources_for_template(self.db)
        tasks_by_level = get_ingestion_tasks_by_level(list(required_resources))

        # Debug logging for resource resolution
        logger.debug(f"{log_ctx} Required resources: {sorted(required_resources)}")
        logger.debug(f"{log_ctx} Tasks by level: {tasks_by_level}")
        logger.debug(f"{log_ctx} Commit SHAs for worktrees: {commit_shas[:5]}...")

        template_repo = DatasetTemplateRepository(self.db)
        template = template_repo.find_by_name("TravisTorrent Full")
        feature_names = template.feature_names if template else []

        repo_config_repo = ModelRepoConfigRepository(self.db)
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "total_builds_imported": len(raw_build_run_ids),
                "feature_extractors": feature_names,
            },
        )

        # Step 3: Create processing task signature
        from app.tasks.model_processing import dispatch_build_processing

        final_task = dispatch_build_processing.si(
            repo_config_id=repo_config_id,
            raw_repo_id=raw_repo_id,
            raw_build_run_ids=raw_build_run_ids,
        )

        # Step 4: Build and execute workflow with processing as final task
        from app.repositories.raw_repository import RawRepositoryRepository

        raw_repo_repo = RawRepositoryRepository(self.db)
        raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
        if not raw_repo:
            raise ValueError(f"RawRepository {raw_repo_id} not found")

        if tasks_by_level:
            from celery import chain as celery_chain

            workflow = build_ingestion_workflow(
                tasks_by_level=tasks_by_level,
                raw_repo_id=raw_repo_id,
                github_repo_id=raw_repo.github_repo_id,
                full_name=full_name,
                build_ids=ci_build_ids,
                commit_shas=commit_shas,
                ci_provider=ci_provider_enum.value,
                correlation_id=correlation_id,
            )
            if workflow:
                # Chain ingestion workflow → processing
                logger.info(f"{log_ctx} Dispatching ingestion workflow -> processing")
                celery_chain(workflow, final_task).apply_async()
            else:
                # No ingestion tasks, run processing directly
                logger.info(f"{log_ctx} No ingestion tasks, running processing directly")
                final_task.apply_async()
        else:
            # No resources needed, run processing directly
            logger.info(f"{log_ctx} No resources needed, running processing directly")
            final_task.apply_async()

        return {
            "status": "dispatched",
            "raw_repo_id": raw_repo_id,
            "builds": len(ci_build_ids),
            "raw_build_run_ids": len(raw_build_run_ids),
            "resources": list(required_resources) if tasks_by_level else [],
            "correlation_id": correlation_id,
        }

    except Exception as e:
        logger.error(f"{log_ctx} Failed to prepare/dispatch processing: {e}")
        from app.entities.enums import ModelImportStatus

        repo_config_repo = ModelRepoConfigRepository(self.db)
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "import_status": ModelImportStatus.FAILED.value,
                "last_sync_status": "failed",
                "last_sync_error": str(e),
            },
        )
        publish_status(repo_config_id, "failed", str(e))
        raise

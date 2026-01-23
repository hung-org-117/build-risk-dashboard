"""
Model Ingestion Fetch Tasks.

Tasks for fetching builds from CI providers:
- fetch_builds_until_existing: Sequential fetch until hitting existing builds
- fetch_builds_batch: Fetch a single page of builds
- aggregate_fetch_results: Aggregate chord results and dispatch ingestion
- handle_fetch_chord_error: Error handler for fetch chord
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.celery_app import celery_app
from app.ci_providers import CIProvider, get_ci_provider, get_provider_config
from app.ci_providers.models import BuildConclusion, BuildStatus
from app.entities.model_import_build import ModelImportBuild, ModelImportBuildStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_import_build import ModelImportBuildRepository
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState, TransientError
from app.tasks.model.ingestion.common import create_repo_config_failure_handler
from app.tasks.model_processing import publish_status

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.fetch.sequential",
    queue="model_ingestion",
    soft_time_limit=600,
    time_limit=900,
)
def fetch_builds_until_existing(
    self: SafeTask,
    repo_config_id: str,
    ci_provider: str,
    batch_size: int,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Sequential fetch that stops when hitting existing builds."""
    # Import here to avoid circular imports
    from app.tasks.model.ingestion.dispatch import dispatch_ingestion_batch

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        log_ctx = f"{corr_prefix}[sync_until_existing]"

        repo_config_repo = ModelRepoConfigRepository(self.db)
        build_run_repo = RawBuildRunRepository(self.db)
        import_build_repo = ModelImportBuildRepository(self.db)
        raw_repo_repo = RawRepositoryRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            return {"status": "error", "error": "Config not found"}

        raw_repo_id = str(repo_config.raw_repo_id)
        full_name = repo_config.full_name

        ci_provider_enum = CIProvider(ci_provider)
        provider_config = get_provider_config(ci_provider_enum, db=self.db)
        ci_instance = get_ci_provider(ci_provider_enum, provider_config, db=self.db)

        raw_repo = raw_repo_repo.find_by_id(repo_config.raw_repo_id)
        if not raw_repo:
            return {"status": "error", "error": "RawRepository not found"}

        since_dt = import_build_repo.get_latest_ingested_run_created_at(repo_config_id)

        if since_dt:
            logger.info(f"{log_ctx} Fetching builds newer than {since_dt.isoformat()}")
        else:
            logger.info(f"{log_ctx} No existing builds, fetching all")

        page = 1
        total_new_builds = 0
        all_commit_shas = []
        all_ci_run_ids = []

        while True:
            logger.info(f"{log_ctx} Fetching page {page}")

            fetch_kwargs = {
                "since": since_dt,
                "limit": batch_size,
                "page": page,
                "exclude_bots": True,
                "only_completed": True,
            }

            try:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    builds = loop.run_until_complete(
                        ci_instance.fetch_builds(full_name, **fetch_kwargs)
                    )
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
            except Exception as e:
                raise TransientError(f"Failed to fetch builds from CI API: {e}") from e

            if not builds:
                logger.info(f"{log_ctx} Page {page}: No builds returned, stopping")
                break

            new_on_page = 0
            existing_on_page = 0

            for build in builds:
                if build.status != BuildStatus.COMPLETED:
                    continue

                if build.conclusion not in (
                    BuildConclusion.SUCCESS,
                    BuildConclusion.FAILURE,
                ):
                    continue

                if not build.build_id:
                    continue

                existing_run = build_run_repo.find_by_repo_and_build_id(
                    raw_repo_id, build.build_id
                )

                if existing_run:
                    existing_on_page += 1
                    continue

                raw_build_run = build_run_repo.upsert_by_business_key(
                    raw_repo_id=ObjectId(raw_repo_id),
                    build_id=build.build_id,
                    provider=ci_provider_enum.value,
                    build_number=build.build_number,
                    repo_name=full_name,
                    branch=build.branch or "",
                    commit_sha=build.commit_sha,
                    commit_message=build.commit_message,
                    commit_author=build.commit_author,
                    status=build.status,
                    conclusion=build.conclusion,
                    run_created_at=build.created_at or datetime.now(timezone.utc),
                    run_started_at=build.started_at or datetime.now(timezone.utc),
                    run_completed_at=build.completed_at
                    or build.started_at
                    or datetime.now(timezone.utc),
                    duration_seconds=build.duration_seconds,
                    web_url=build.web_url,
                    logs_url=None,
                    logs_available=build.logs_available or False,
                    logs_path=None,
                    raw_data=build.raw_data or {},
                    is_bot_commit=build.is_bot_commit or False,
                )

                import_build_repo.upsert_by_business_key(
                    config_id=repo_config_id,
                    raw_build_run_id=str(raw_build_run.id),
                    status=ModelImportBuildStatus.FETCHED,
                    ci_run_id=raw_build_run.ci_run_id,
                    commit_sha=build.commit_sha or "",
                )

                new_on_page += 1
                all_commit_shas.append(build.commit_sha)
                all_ci_run_ids.append(build.build_id)

            total_new_builds += new_on_page
            logger.info(
                f"{log_ctx} Page {page}: {new_on_page} new, {existing_on_page} existing"
            )

            if existing_on_page > 0:
                logger.info(
                    f"{log_ctx} Found {existing_on_page} existing builds, stopping sync"
                )
                break

            if len(builds) < batch_size:
                logger.info(
                    f"{log_ctx} No more pages (got {len(builds)} < {batch_size})"
                )
                break

            page += 1

        logger.info(f"{log_ctx} Sync complete: {total_new_builds} new builds found")

        repo_config_repo.increment_builds_fetched(
            ObjectId(repo_config_id),
            total_new_builds,
        )

        if total_new_builds == 0:
            publish_status(repo_config_id, "processed", "No new builds found")
            repo_config_repo.update_repository(
                repo_config_id,
                {"status": ModelImportStatus.PROCESSED.value},
            )
            return {"status": "completed", "new_builds": 0, "pages": page}

        # Mark as FETCHED before starting ingestion
        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.FETCHED.value},
        )
        publish_status(
            repo_config_id,
            "fetched",
            f"Fetch complete: {total_new_builds} builds ready for ingestion",
            stats={"builds_fetched": total_new_builds},
        )

        dispatch_ingestion_batch.delay(
            repo_config_id=repo_config_id,
            raw_repo_id=raw_repo_id,
            github_repo_id=raw_repo.github_repo_id,
            full_name=full_name,
            ci_provider=ci_provider,
            commit_shas=list(set(all_commit_shas)),
            ci_run_ids=list(set(all_ci_run_ids)),
            correlation_id=correlation_id,
        )

        publish_status(
            repo_config_id,
            "ingesting",
            f"Preparing resources for {total_new_builds} new builds...",
            stats={
                "builds_fetched": total_new_builds,
                "builds_features_extracted": 0,
                "builds_missing_resource": 0,
            },
        )

        return {
            "status": "dispatched",
            "new_builds": total_new_builds,
            "pages": page,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.fetch.page",
    queue="model_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def fetch_builds_page(
    self: SafeTask,
    repo_config_id: str,
    ci_provider: str,
    page: int,
    batch_size: int,
    since_days: Optional[int] = None,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Fetch a single page of builds and create ModelImportBuild records."""

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        log_ctx = f"{corr_prefix}[fetch_batch][page={page}]"

        repo_config_repo = ModelRepoConfigRepository(self.db)
        build_run_repo = RawBuildRunRepository(self.db)
        import_build_repo = ModelImportBuildRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            return {"page": page, "builds": 0, "error": "Config not found"}

        raw_repo_id = str(repo_config.raw_repo_id)
        full_name = repo_config.full_name

        since_dt = (
            datetime.now(timezone.utc) - timedelta(days=since_days)
            if since_days
            else None
        )

        ci_provider_enum = CIProvider(ci_provider)
        provider_config = get_provider_config(ci_provider_enum, db=self.db)
        ci_instance = get_ci_provider(ci_provider_enum, provider_config, db=self.db)

        fetch_kwargs = {
            "since": since_dt,
            "limit": batch_size,
            "page": page,
            "exclude_bots": True,
            "only_completed": True,
        }

        try:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                builds = loop.run_until_complete(
                    ci_instance.fetch_builds(full_name, **fetch_kwargs)
                )
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as e:
            raise TransientError(f"Failed to fetch builds page {page}: {e}") from e

        if not builds:
            logger.info(f"{log_ctx} No builds found")
            return {"page": page, "builds": 0, "has_more": False}

        import_builds_to_insert = []

        for build in builds:
            if build.status != BuildStatus.COMPLETED:
                continue

            if build.conclusion not in (
                BuildConclusion.SUCCESS,
                BuildConclusion.FAILURE,
            ):
                continue

            if not build.build_id:
                logger.warning(
                    f"{log_ctx} Skipping build with null build_id: "
                    f"build_number={build.build_number}"
                )
                continue

            raw_build_run = build_run_repo.upsert_by_business_key(
                raw_repo_id=ObjectId(raw_repo_id),
                build_id=build.build_id,
                provider=ci_provider_enum.value,
                build_number=build.build_number,
                repo_name=full_name,
                branch=build.branch or "",
                commit_sha=build.commit_sha,
                commit_message=build.commit_message,
                commit_author=build.commit_author,
                status=build.status,
                conclusion=build.conclusion,
                run_created_at=build.created_at or datetime.now(timezone.utc),
                run_started_at=build.started_at,
                run_completed_at=build.completed_at
                or build.created_at
                or datetime.now(timezone.utc),
                duration_seconds=build.duration_seconds,
                web_url=build.web_url,
                logs_url=None,
                logs_available=build.logs_available or False,
                logs_path=None,
                raw_data=build.raw_data or {},
                is_bot_commit=build.is_bot_commit or False,
            )

            existing = import_build_repo.find_by_business_key(
                repo_config_id, str(raw_build_run.id)
            )
            if existing:
                continue

            import_build = ModelImportBuild(
                _id=None,
                model_repo_config_id=ObjectId(repo_config_id),
                raw_build_run_id=raw_build_run.id,
                status=ModelImportBuildStatus.FETCHED,
                ci_run_id=raw_build_run.ci_run_id,
                commit_sha=build.commit_sha or "",
                run_created_at=raw_build_run.run_created_at,
                ingestion_started_at=None,
                ingested_at=None,
                ingestion_error=None,
            )
            import_builds_to_insert.append(import_build)

        if import_builds_to_insert:
            import_build_repo.bulk_insert(import_builds_to_insert)

        has_more = len(builds) >= batch_size
        logger.info(
            f"{log_ctx} Saved {len(import_builds_to_insert)} builds, has_more={has_more}"
        )

        return {
            "page": page,
            "builds": len(import_builds_to_insert),
            "has_more": has_more,
        }

    return self.run_safe(
        job_id=f"{repo_config_id}:{page}",
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.fetch.complete",
    queue="model_ingestion",
    soft_time_limit=60,
    time_limit=120,
)
def handle_fetch_completion(
    self: SafeTask,
    results: List[Dict[str, Any]],
    repo_config_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Aggregate fetch results and dispatch ingestion."""
    from app.tasks.model.ingestion.dispatch import dispatch_ingestion_batch

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        log_ctx = f"{corr_prefix}[aggregate_fetch]"

        import_build_repo = ModelImportBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)
        raw_repo_repo = RawRepositoryRepository(self.db)

        total_from_results = sum(r.get("builds", 0) for r in results if r)
        logger.info(
            f"{log_ctx} Chord results: {total_from_results} builds from {len(results)} tasks"
        )

        if total_from_results == 0:
            repo_config_repo.update_repository(
                repo_config_id,
                {
                    "status": ModelImportStatus.PROCESSED.value,
                    "builds_fetched": 0,
                },
            )
            publish_status(repo_config_id, "processed", "No builds found")
            return {"status": "completed", "builds": 0}

        fetched_builds = import_build_repo.find_fetched_builds(repo_config_id)
        total_fetched = len(fetched_builds)

        if total_fetched != total_from_results:
            logger.warning(
                f"{log_ctx} Discrepancy: chord={total_from_results}, db={total_fetched}"
            )

        logger.info(f"{log_ctx} Found {total_fetched} fetched builds in DB")

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            raise ValueError(f"ModelRepoConfig {repo_config_id} not found")

        repo_config_repo.update_repository(
            repo_config_id,
            {
                "builds_fetched": total_fetched,
                "status": ModelImportStatus.FETCHED.value,
            },
        )

        publish_status(
            repo_config_id,
            "fetched",
            f"Fetch complete: {total_fetched} builds ready for ingestion",
            stats={"builds_fetched": total_fetched},
        )

        commit_shas = import_build_repo.get_commit_shas(repo_config_id)
        ci_run_ids = import_build_repo.get_ci_run_ids(repo_config_id)

        raw_repo = raw_repo_repo.find_by_id(repo_config.raw_repo_id)
        if not raw_repo:
            raise ValueError(f"RawRepository {repo_config.raw_repo_id} not found")

        dispatch_ingestion_batch.delay(
            repo_config_id=repo_config_id,
            raw_repo_id=str(repo_config.raw_repo_id),
            github_repo_id=raw_repo.github_repo_id,
            full_name=repo_config.full_name,
            ci_provider=repo_config.ci_provider,
            commit_shas=commit_shas,
            ci_run_ids=ci_run_ids,
            correlation_id=correlation_id,
        )

        publish_status(
            repo_config_id,
            "ingesting",
            f"Preparing resources for {total_fetched} builds...",
            stats={
                "builds_fetched": total_fetched,
                "builds_ingested": 0,
            },
        )

        return {
            "status": "dispatched",
            "builds": total_fetched,
            "commits": len(commit_shas),
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_ingestion.handle_fetch_chord_error",
    queue="model_ingestion",
    soft_time_limit=30,
    time_limit=60,
)
def handle_fetch_chord_error(
    self: PipelineTask,
    request,
    exc,
    traceback,
    repo_config_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Error callback for fetch chord failure."""
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    error_msg = str(exc) if exc else "Unknown fetch error"

    logger.error(f"{corr_prefix} Fetch chord failed for {repo_config_id}: {error_msg}")

    repo_config_repo = ModelRepoConfigRepository(self.db)

    repo_config_repo.update_repository(
        repo_config_id,
        {
            "status": ModelImportStatus.FAILED.value,
            "error_message": f"Fetch failed: {error_msg}",
            "ingested_at": datetime.utcnow(),
        },
    )

    publish_status(
        repo_config_id,
        "failed",
        f"Failed to fetch builds: {error_msg}",
    )

    return {
        "status": "handled",
        "error": error_msg,
        "repo_config_id": repo_config_id,
    }


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.fetch.webhook",
    queue="model_ingestion",
    soft_time_limit=300,
    time_limit=360,
)
def fetch_webhook_build(
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
    It creates a ModelImportBuild (FETCHED) and dispatches ingestion.
    """
    import uuid
    from app.tasks.model.ingestion.dispatch import dispatch_ingestion_batch

    correlation_id = str(uuid.uuid4())[:8]
    corr_prefix = f"[corr={correlation_id}][webhook]"

    logger.info(
        f"{corr_prefix} Starting webhook ingestion for build {ci_run_id} "
        f"in repo {full_name}"
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

    existing_import = import_build_repo.find_by_business_key(
        repo_config_id, raw_build_run_id
    )

    if existing_import:
        logger.info(f"{corr_prefix} Build {ci_run_id} already ingested, skipping")
        return {"status": "already_ingested", "build_id": ci_run_id}

    from app.repositories.raw_build_run import RawBuildRunRepository

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

    dispatch_ingestion_batch.delay(
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

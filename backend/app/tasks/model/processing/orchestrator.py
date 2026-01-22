"""
Model Processing Orchestrator Tasks.

Entry point tasks for model processing pipeline:
- start_processing_phase: Entry point (user-triggered)
- dispatch_build_processing: Dispatch feature extraction tasks
"""

import logging
import uuid
from typing import Any, Dict, List

from bson import ObjectId
from celery import chain

from app.celery_app import celery_app
from app.core.tracing import TracingContext
from app.entities.enums import ExtractionStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_import_build import ModelImportBuildRepository
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.model_training_build import ModelTrainingBuildRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.model.processing.common import (
    create_repo_config_failure_handler,
    publish_status,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_processing.start_processing_phase",
    queue="model_processing",
    soft_time_limit=60,
    time_limit=120,
)
def start_processing_phase(
    self: SafeTask,
    repo_config_id: str,
) -> Dict[str, Any]:
    """Phase 2: Start processing phase (manually triggered by user)."""
    # Import here to avoid circular imports
    from app.tasks.model.processing.orchestrator import dispatch_build_processing

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        correlation_id = TracingContext.get_correlation_id() or str(uuid.uuid4())
        log_ctx = f"[corr={correlation_id[:8]}]"

        import_build_repo = ModelImportBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            logger.error(f"{log_ctx} Repository config {repo_config_id} not found")
            return {"status": "error", "message": "Repository config not found"}

        valid_statuses = [
            ModelImportStatus.INGESTED.value,
            ModelImportStatus.PROCESSED.value,
        ]
        if repo_config.status not in valid_statuses:
            msg = (
                f"Cannot start processing: status is {repo_config.status}. "
                f"Expected: {valid_statuses}"
            )
            logger.warning(f"{log_ctx} {msg}")
            return {"status": "error", "message": msg}

        last_checkpoint_id = repo_config.last_processed_import_build_id

        if last_checkpoint_id:
            logger.info(f"{log_ctx} Checkpoint exists at {last_checkpoint_id}, finding new builds")
        else:
            logger.info(f"{log_ctx} No checkpoint, processing all builds")

        pending_builds = import_build_repo.find_unprocessed_builds(
            repo_config_id, after_id=last_checkpoint_id, include_failed=True
        )

        if not pending_builds:
            logger.info(f"{log_ctx} No new builds to process for {repo_config_id}")
            return {
                "status": "completed",
                "builds": 0,
                "message": "No new builds to process",
            }

        last_build_id = pending_builds[-1].id

        ingested_count = sum(1 for b in pending_builds if b.status == "ingested")
        failed_count = sum(1 for b in pending_builds if b.status == "failed")

        logger.info(
            f"{log_ctx} Processing {len(pending_builds)} builds "
            f"({ingested_count} ingested, {failed_count} failed)"
        )

        model_import_build_ids = [str(b.id) for b in pending_builds]

        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.PROCESSING.value},
        )

        dispatch_build_processing.delay(
            repo_config_id=repo_config_id,
            raw_repo_id=str(repo_config.raw_repo_id),
            model_import_build_ids=model_import_build_ids,
            correlation_id=correlation_id,
            last_import_build_id=str(last_build_id),
        )

        logger.info(f"{log_ctx} Dispatched processing for {len(model_import_build_ids)} builds")

        publish_status(
            repo_config_id,
            "processing",
            f"Processing {len(model_import_build_ids)} builds...",
        )

        return {
            "status": "dispatched",
            "builds": len(model_import_build_ids),
            "ingested": ingested_count,
            "failed": failed_count,
            "pending_checkpoint_id": str(last_build_id),
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_processing.dispatch_build_processing",
    queue="model_processing",
    soft_time_limit=300,
    time_limit=360,
)
def dispatch_build_processing(
    self: SafeTask,
    repo_config_id: str,
    raw_repo_id: str,
    model_import_build_ids: List[str],
    correlation_id: str = "",
    last_import_build_id: str = "",
) -> Dict[str, Any]:
    """Create ModelTrainingBuild docs and dispatch feature extraction tasks."""
    # Import here to avoid circular imports
    from app.tasks.model.processing.extraction import process_workflow_run
    from app.tasks.model.processing.prediction import (
        finalize_model_processing,
        handle_processing_chain_error,
    )

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

        model_build_repo = ModelTrainingBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)
        raw_build_run_repo = RawBuildRunRepository(self.db)
        import_build_repo = ModelImportBuildRepository(self.db)

        if not model_import_build_ids:
            logger.info(f"{corr_prefix} No builds to process for repo config {repo_config_id}")
            repo_config_repo.update_repository(
                repo_config_id,
                {"status": ModelImportStatus.PROCESSED.value},
            )
            publish_status(repo_config_id, "processed", "No new builds to process")
            return {"repo_config_id": repo_config_id, "dispatched": 0}

        ingested_builds = import_build_repo.find_many(
            {"_id": {"$in": [ObjectId(bid) for bid in model_import_build_ids]}},
            sort=[("run_created_at", 1)],
        )

        raw_build_run_ids = [str(b.raw_build_run_id) for b in ingested_builds]
        raw_build_runs = raw_build_run_repo.find_by_ids(raw_build_run_ids)
        build_run_map = {str(r.id): r for r in raw_build_runs}

        run_oids = [ObjectId(rid) for rid in raw_build_run_ids if ObjectId.is_valid(rid)]
        existing_builds_map = model_build_repo.find_existing_by_raw_build_run_ids(
            ObjectId(raw_repo_id), run_oids
        )

        created_count = 0
        skipped_existing = 0
        model_build_ids = []

        for import_build in ingested_builds:
            run_id_str = str(import_build.raw_build_run_id)

            raw_build_run = build_run_map.get(run_id_str)
            if not raw_build_run:
                logger.warning(f"{corr_prefix} RawBuildRun {run_id_str} not found, skipping")
                continue

            existing = existing_builds_map.get(run_id_str)
            if existing and existing.extraction_status != ExtractionStatus.PENDING:
                logger.debug(
                    f"ModelTrainingBuild already processed ({existing.extraction_status}), "
                    f"skipping: {run_id_str}"
                )
                skipped_existing += 1
                continue

            model_build, was_created = model_build_repo.upsert_or_get(
                raw_repo_id=ObjectId(raw_repo_id),
                raw_build_run_id=ObjectId(run_id_str),
                model_import_build_id=import_build.id,
                model_repo_config_id=ObjectId(repo_config_id),
                head_sha=raw_build_run.commit_sha,
                build_number=raw_build_run.build_number,
                build_created_at=raw_build_run.run_created_at,
                extraction_status=ExtractionStatus.PENDING,
            )
            model_build_ids.append(model_build.id)
            if was_created:
                created_count += 1

        logger.info(
            f"{corr_prefix} Created {created_count} new builds, "
            f"skipped {skipped_existing} already processed, "
            f"dispatching {len(model_build_ids)} for processing"
        )

        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.PROCESSING.value},
        )
        publish_status(
            repo_config_id,
            "processing",
            f"Scheduling {len(model_build_ids)} builds for sequential processing...",
            stats={
                "builds_ingested": len(raw_build_run_ids),
                "builds_created": created_count,
                "builds_skipped": skipped_existing,
            },
        )

        model_build_id_strs = [str(bid) for bid in model_build_ids]
        total_builds = len(model_build_id_strs)

        if total_builds == 0:
            repo_config_repo.update_repository(
                repo_config_id,
                {"status": ModelImportStatus.PROCESSED.value},
            )
            publish_status(repo_config_id, "processed", "No pending builds to process")
            return {"repo_config_id": repo_config_id, "dispatched": 0}

        sequential_tasks = [
            process_workflow_run.si(
                repo_config_id=repo_config_id,
                model_build_id=build_id,
                is_reprocess=False,
                correlation_id=correlation_id,
            )
            for build_id in model_build_id_strs
        ]

        logger.info(f"{corr_prefix} Dispatching {total_builds} builds for sequential processing")

        workflow = chain(
            *sequential_tasks,
            finalize_model_processing.si(
                repo_config_id=repo_config_id,
                created_count=created_count,
                correlation_id=correlation_id,
                last_import_build_id=last_import_build_id,
            ),
        )

        error_callback = handle_processing_chain_error.s(
            repo_config_id=repo_config_id,
            correlation_id=correlation_id,
        )
        workflow.on_error(error_callback).apply_async()

        publish_status(
            repo_config_id,
            "processing",
            f"Processing {total_builds} builds sequentially (oldest → newest)...",
        )

        return {
            "repo_config_id": repo_config_id,
            "dispatched": total_builds,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )

"""
Model Processing Retry Task.

Retry failed builds:
- retry_failed_builds: Retry extraction and/or prediction failures
"""

import logging
import uuid
from typing import Any, Dict

from bson import ObjectId
from celery import chain, group

from app.celery_app import celery_app
from app.config import settings
from app.core.tracing import TracingContext
from app.entities.enums import ExtractionStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.model_training_build import ModelTrainingBuildRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.model.processing.common import (
    create_repo_config_failure_handler,
    publish_status,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.model_processing.retry_failed_builds",
    queue="model_processing",
    soft_time_limit=300,
    time_limit=360,
)
def retry_failed_builds(self: SafeTask, repo_config_id: str) -> Dict[str, Any]:
    """
    Retry for failed builds - handles both extraction and prediction failures.

    Logic:
    1. Extraction FAILED builds → full pipeline (extract + predict)
    2. Extraction COMPLETED + Prediction FAILED → predict only (skip extraction)
    """
    # Import here to avoid circular imports
    from app.tasks.model.processing.extraction import process_workflow_run
    from app.tasks.model.processing.prediction import (
        finalize_model_processing,
        predict_batch,
    )

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(self.redis, repo_config_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        correlation_id = str(uuid.uuid4())
        TracingContext.set(
            correlation_id=correlation_id,
            repo_id=repo_config_id,
            pipeline_type="retry_failed",
        )

        corr_prefix = f"[corr={correlation_id[:8]}]"
        model_build_repo = ModelTrainingBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        if not repo_config:
            logger.error(f"{corr_prefix} Repository Config {repo_config_id} not found")
            return {"status": "error", "message": "Repository Config not found"}

        extraction_failed_builds = model_build_repo.find_failed_builds(ObjectId(repo_config_id))
        extraction_failed_builds.sort(key=lambda b: b.build_created_at or b.created_at)

        prediction_failed_builds = model_build_repo.find_builds_with_failed_predictions(
            ObjectId(repo_config_id)
        )

        extraction_count = len(extraction_failed_builds)
        prediction_count = len(prediction_failed_builds)

        if extraction_count == 0 and prediction_count == 0:
            logger.info(f"{corr_prefix} No failed builds found for repository {repo_config_id}")
            return {
                "status": "completed",
                "extraction_failed": 0,
                "prediction_failed": 0,
                "message": "No failed builds to retry",
            }

        logger.info(
            f"{corr_prefix} Found {extraction_count} extraction failures, "
            f"{prediction_count} prediction failures"
        )

        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.PROCESSING.value},
        )
        publish_status(
            repo_config_id,
            "processing",
            f"Retrying: {extraction_count} extraction + {prediction_count} prediction failures...",
        )

        extraction_build_ids = []
        for build in extraction_failed_builds:
            try:
                model_build_repo.update_one(
                    str(build.id),
                    {
                        "extraction_status": ExtractionStatus.PENDING.value,
                        "extraction_error": None,
                    },
                )
                extraction_build_ids.append(str(build.id))
            except Exception as e:
                logger.warning(f"{corr_prefix} Failed to reset build {build.id}: {e}")

        prediction_only_ids = []
        for build in prediction_failed_builds:
            try:
                model_build_repo.update_one(
                    str(build.id),
                    {
                        "prediction_status": ExtractionStatus.PENDING.value,
                        "prediction_error": None,
                        "predicted_label": None,
                    },
                )
                prediction_only_ids.append(str(build.id))
            except Exception as e:
                logger.warning(f"{corr_prefix} Failed to reset prediction for {build.id}: {e}")

        tasks_dispatched = 0

        if extraction_build_ids:
            processing_tasks = [
                process_workflow_run.si(
                    repo_config_id=repo_config_id,
                    model_build_id=build_id,
                    is_reprocess=True,
                    correlation_id=correlation_id,
                )
                for build_id in extraction_build_ids
            ]

            workflow = chain(
                *processing_tasks,
                finalize_model_processing.si(
                    repo_config_id=repo_config_id,
                    created_count=len(extraction_build_ids),
                    correlation_id=correlation_id,
                ),
            )
            workflow.apply_async()
            tasks_dispatched += len(extraction_build_ids)
            logger.info(f"{corr_prefix} Dispatched {len(extraction_build_ids)} extraction tasks")

        if prediction_only_ids:
            batch_size = settings.PREDICTION_BUILDS_PER_BATCH
            batches = [
                prediction_only_ids[i : i + batch_size]
                for i in range(0, len(prediction_only_ids), batch_size)
            ]
            prediction_tasks = [
                predict_batch.si(
                    repo_config_id=repo_config_id,
                    model_build_ids=batch,
                )
                for batch in batches
            ]
            group(prediction_tasks).apply_async()
            tasks_dispatched += len(prediction_only_ids)
            logger.info(
                f"{corr_prefix} Dispatched {len(prediction_only_ids)} prediction-only builds "
                f"in {len(batches)} batches"
            )

        return {
            "status": "queued",
            "extraction_retries": len(extraction_build_ids),
            "prediction_retries": len(prediction_only_ids),
            "total_dispatched": tasks_dispatched,
            "correlation_id": correlation_id,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )

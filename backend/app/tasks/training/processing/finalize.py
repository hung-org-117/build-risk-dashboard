"""
Training Processing - Finalize Tasks.

Contains:
- finalize_feature_extraction: Finalize after all builds processed
- handle_processing_chain_error: Error handler for chain failures
"""

import logging
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated
from app.tasks.training.processing.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.finalize_feature_extraction",
    queue="scenario_processing",
    soft_time_limit=160,
    time_limit=220,
)
def finalize_feature_extraction(
    self: SafeTask,
    scenario_id: str,
    created_count: int = 0,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Finalize feature extraction phase after all builds have been processed.

    Marks feature_extraction_completed=True. Scenario stays in PROCESSED status.
    Scans may still be running in parallel.
    """

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(f"{corr_prefix} [finalize_processing] Finalizing for {scenario_id}")

        scenario_repo = TrainingScenarioRepository(self.db)
        enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)

        # Get stats
        stats = enrichment_build_repo.aggregate_stats_by_scenario(scenario_id)
        completed = stats.get("completed", 0)
        partial = stats.get("partial", 0)
        failed = stats.get("failed", 0)
        total = completed + partial + failed

        # Update scenario - mark as PROCESSED
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSED.value,
                    "builds_features_extracted": completed + partial,
                    "builds_features_extracted_failed": failed,
                    "processing_completed_at": datetime.utcnow(),
                    "feature_extraction_completed": True,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario)

            logger.info(
                f"{corr_prefix} Completed: {completed + partial}/{total}, failed: {failed}. "
            )

            # Trigger feature quality evaluation after feature extraction
            try:
                from app.services.data_quality_service import DataQualityService

                quality_service = DataQualityService(self.db)
                quality_service.finalize_feature_quality_report(scenario_id)
                logger.info(f"{corr_prefix} Feature quality report finalized for {scenario_id}")
            except Exception as e:
                logger.warning(f"{corr_prefix} Quality evaluation failed: {e}")

            return {
                "status": "completed",
                "builds_features_extracted": completed + partial,
                "builds_features_extracted_failed": failed,
                "total": total,
            }

        return {"status": "error", "error": "Scenario not found"}

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_processing.handle_processing_chain_error",
    queue="scenario_processing",
    soft_time_limit=60,
    time_limit=120,
)
def handle_processing_chain_error(
    self: PipelineTask,
    request,
    exc,
    traceback,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Error callback for processing chain failure.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    error_msg = str(exc) if exc else "Unknown processing error"

    logger.error(f"{corr_prefix} Processing chain failed for {scenario_id}: {error_msg}")

    enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)
    scenario_repo = TrainingScenarioRepository(self.db)

    now = datetime.utcnow()

    # Mark all IN_PROGRESS enrichment builds as FAILED
    failed_count = enrichment_build_repo.collection.update_many(
        {
            "scenario_id": ObjectId(scenario_id),
            "extraction_status": ExtractionStatus.IN_PROGRESS.value,
        },
        {
            "$set": {
                "extraction_status": ExtractionStatus.FAILED.value,
                "extraction_error": f"Chain failed: {error_msg}",
            }
        },
    ).modified_count

    # Count completed builds
    completed_count = enrichment_build_repo.collection.count_documents(
        {
            "scenario_id": ObjectId(scenario_id),
            "extraction_status": ExtractionStatus.COMPLETED.value,
        }
    )

    if completed_count > 0:
        # Some builds completed - mark as PROCESSED
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSED.value,
                    "builds_features_extracted": completed_count,
                    "builds_features_extracted_failed": failed_count,
                    "processing_completed_at": now,
                    "feature_extraction_completed": True,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario)
    else:
        # No builds completed - mark as FAILED and notify
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.FAILED.value,
                    "error_message": error_msg,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario, error=error_msg)

        # Notify failure
        from app.services.notification_service import notify_training_scenario_failed

        notify_training_scenario_failed(
            db=self.db,
            scenario_id=scenario_id,
            error_message=error_msg,
            completed_count=completed_count,
            failed_count=failed_count,
        )

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "completed_builds": completed_count,
        "error": error_msg,
    }

"""
Training Ingestion - Aggregate and Error Handler Tasks.

Contains:
- aggregate_scenario_ingestion: Chord callback to aggregate results
- handle_scenario_chord_error: Error handler for chord failures
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated
from app.tasks.training.ingestion.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_ingestion.aggregate_scenario_ingestion",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def aggregate_scenario_ingestion(
    self: SafeTask,
    results: List[Dict[str, Any]],
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Chord callback: Aggregate ingestion results and mark scenario as INGESTED.

    After all repo ingestion chains complete, marks builds as INGESTED/FAILED.
    Does NOT auto-dispatch processing - user triggers Phase 2 manually.
    """

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(f"{corr_prefix} [aggregate_ingestion] Processing results for {scenario_id}")

        scenario_repo = TrainingScenarioRepository(self.db)
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)

        now = datetime.utcnow()

        # Determine per-build final status from resource_status in DB
        # 1. Check if git_history failed (affects ALL builds)
        git_history_failed = ingestion_build_repo.collection.count_documents(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.INGESTING.value,
                "resource_status.git_history.status": "failed",
            }
        )

        if git_history_failed > 0:
            # Clone failed - mark all as FAILED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                },
                {
                    "$set": {
                        "status": IngestionStatus.FAILED.value,
                        "ingestion_error": "Clone failed",
                        "ingested_at": now,
                    }
                },
            )
        else:
            # 2. Mark builds with failed git_worktree as FAILED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                    "resource_status.git_worktree.status": "failed",
                },
                {
                    "$set": {
                        "status": IngestionStatus.FAILED.value,
                        "ingestion_error": "Worktree creation failed",
                        "ingested_at": now,
                    }
                },
            )

            # 3. Mark builds with failed build_logs as MISSING_RESOURCE
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                    "resource_status.build_logs.status": "failed",
                },
                {
                    "$set": {
                        "status": IngestionStatus.MISSING_RESOURCE.value,
                        "ingestion_error": "Log download failed or expired",
                        "ingested_at": now,
                    }
                },
            )

            # 4. Mark remaining INGESTING builds as INGESTED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                },
                {
                    "$set": {
                        "status": IngestionStatus.INGESTED.value,
                        "ingested_at": now,
                    }
                },
            )

        # Count by status
        status_counts = ingestion_build_repo.count_by_status(scenario_id)
        ingested = status_counts.get(IngestionStatus.INGESTED.value, 0)
        missing_resource = status_counts.get(IngestionStatus.MISSING_RESOURCE.value, 0)
        failed = status_counts.get(IngestionStatus.FAILED.value, 0)

        # Update scenario atomically and get result
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.INGESTED.value,
                    "builds_ingested": ingested,
                    "builds_missing_resource": missing_resource,
                    "builds_ingestion_failed": failed,
                    "ingestion_completed_at": now,
                }
            },
            return_updated=True,
        )

        # Build status message
        if failed > 0 or missing_resource > 0:
            parts = [f"{ingested} ready"]
            if failed > 0:
                parts.append(f"{failed} failed (retryable)")
            if missing_resource > 0:
                parts.append(f"{missing_resource} missing resources")
            msg = f"Ingestion done: {', '.join(parts)}. Start processing when ready."
        else:
            msg = f"Ingestion complete: {ingested} builds ready. Start processing when ready."

        logger.info(f"{corr_prefix} [aggregate_ingestion] {msg}")

        # Final update - publish scenario aggregate status
        scenario = scenario_repo.find_by_id(scenario_id)
        if scenario:
            publish_scenario_updated(scenario)

        return {
            "status": "completed",
            "final_status": ScenarioStatus.INGESTED.value,
            "builds_ingested": ingested,
            "builds_missing_resource": missing_resource,
            "builds_ingestion_failed": failed,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_ingestion.handle_scenario_chord_error",
    queue="scenario_ingestion",
    soft_time_limit=60,
    time_limit=120,
)
def handle_scenario_chord_error(
    self: PipelineTask,
    task_id: str,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Error callback for ingestion chord failure.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # Try to get error info
    error_msg = "Unknown ingestion error"
    try:
        result = AsyncResult(task_id)
        if isinstance(result.result, Exception):
            error_msg = str(result.result)
        elif result.result:
            error_msg = str(result.result)
    except Exception as e:
        logger.warning(f"Could not retrieve exception for task {task_id}: {e}")

    logger.error(f"{corr_prefix} Ingestion chord failed for scenario {scenario_id}: {error_msg}")

    ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
    scenario_repo = TrainingScenarioRepository(self.db)

    now = datetime.utcnow()

    # Mark all INGESTING builds as FAILED
    failed_count = ingestion_build_repo.collection.update_many(
        {
            "scenario_id": ObjectId(scenario_id),
            "status": IngestionStatus.INGESTING.value,
        },
        {
            "$set": {
                "status": IngestionStatus.FAILED.value,
                "ingestion_error": f"Ingestion chord failed: {error_msg}",
                "ingested_at": now,
            }
        },
    ).modified_count

    # Check if any builds made it to INGESTED
    ingested_count = ingestion_build_repo.collection.count_documents(
        {
            "scenario_id": ObjectId(scenario_id),
            "status": IngestionStatus.INGESTED.value,
        }
    )

    if ingested_count > 0:
        # Some builds made it through
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.INGESTED.value,
                    "builds_ingested": ingested_count,
                    "builds_ingestion_failed": failed_count,
                    "ingestion_completed_at": now,
                }
            },
            return_updated=True,
        )
        if scenario:
            publish_scenario_updated(scenario)
    else:
        # No builds made it
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.FAILED.value,
                    "error_message": error_msg,
                }
            },
            return_updated=True,
        )
        if scenario:
            publish_scenario_updated(scenario, error=error_msg)

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "ingested_builds": ingested_count,
        "error": error_msg,
    }

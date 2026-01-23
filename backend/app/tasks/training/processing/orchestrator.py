"""
Training Processing - Orchestrator Tasks.

Contains:
- start_scenario_processing: Entry point (user triggers Phase 2)
- dispatch_scans_and_processing: Dispatch scans + feature extraction
"""

import logging
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.celery_app import celery_app
from app.entities.training_scenario import ScenarioStatus
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated
from app.tasks.training.processing.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.start_scenario_processing",
    queue="scenario_processing",
    soft_time_limit=60,
    time_limit=120,
)
def start_scenario_processing(
    self: SafeTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Phase 2: Start processing phase (manually triggered by user).

    Validates that ingestion is complete before starting feature extraction.
    Only proceeds if status is INGESTED.
    """
    # Import here to avoid circular imports
    from app.tasks.training.processing.enrichment import dispatch_scans_and_processing

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        import uuid

        correlation_id = str(uuid.uuid4())
        logger.info(f"[start_scenario_processing] Starting for scenario {scenario_id}")

        scenario_repo = TrainingScenarioRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Validate status
        if scenario.status != ScenarioStatus.INGESTED.value:
            return {
                "status": "error",
                "error": f"Cannot start processing: status is {scenario.status}, expected INGESTED",
            }

        # Update status to PROCESSING atomically and get updated document
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSING.value,
                    "processing_started_at": datetime.utcnow(),
                    "current_task_id": self.request.id,
                }
            },
            return_updated=True,
        )

        if scenario:
            publish_scenario_updated(scenario)

        # Dispatch scans and processing
        dispatch_scans_and_processing.delay(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        return {
            "status": "dispatched",
            "scenario_id": scenario_id,
            "correlation_id": correlation_id,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )

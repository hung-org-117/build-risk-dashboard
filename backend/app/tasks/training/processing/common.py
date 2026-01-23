"""
Training Processing - Shared Utilities.

Common functions used across processing tasks.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)


def create_scenario_failure_handler(redis, scenario_id: str, db) -> Callable[[str, str], None]:
    """
    Create a failure handler for TrainingScenario orchestrator-level tasks.
    Updates status to FAILED and publishes SSE events.

    Args:
        redis: Redis connection (for compatibility)
        scenario_id: The training scenario ID
        db: MongoDB database connection

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from bson import ObjectId

    from app.entities.training_scenario import ScenarioStatus
    from app.repositories.training_scenario import TrainingScenarioRepository
    from app.tasks.shared.events import publish_scenario_updated

    def handler(status: str, error_message: str) -> None:
        try:
            scenario_repo = TrainingScenarioRepository(db)
            updated_scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "status": ScenarioStatus.FAILED.value,
                        "error_message": error_message[:500],
                    }
                },
                return_updated=True,
            )
            if updated_scenario:
                publish_scenario_updated(updated_scenario, error=error_message)
            logger.info(
                f"Marked TrainingScenario {scenario_id[:8]} as FAILED: {error_message[:100]}"
            )
        except Exception as e:
            logger.warning(f"Failed to mark TrainingScenario {scenario_id[:8]} as FAILED: {e}")

    return handler


def create_training_enrichment_build_failure_handler(
    db, enrichment_build_id: str
) -> Callable[[str, str], None]:
    """
    Create a failure handler for TrainingEnrichmentBuild build-level tasks.
    Updates extraction status to FAILED when processing fails.

    Args:
        db: MongoDB database connection
        enrichment_build_id: The training enrichment build ID

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from app.entities.enums import ExtractionStatus
    from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository

    def handler(status: str, error_message: str) -> None:
        try:
            repo = TrainingEnrichmentBuildRepository(db)
            repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.FAILED,
                error_message=error_message[:500],
            )
            logger.info(
                f"Marked TrainingEnrichmentBuild {enrichment_build_id[:8]} as FAILED: "
                f"{error_message[:100]}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to mark TrainingEnrichmentBuild {enrichment_build_id[:8]} "
                f"as FAILED: {e}"
            )

    return handler

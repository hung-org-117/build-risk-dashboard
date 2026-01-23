"""
Common utilities for model processing tasks.
"""

import logging
from typing import Callable, List

from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.tasks.shared.events import publish_model_repo_updated as publish_status

logger = logging.getLogger(__name__)


def create_repo_config_failure_handler(
    redis_client, repo_config_id: str, db
) -> Callable[[str, str], None]:
    """
    Create a failure handler for ModelRepoConfig orchestrator-level tasks.
    Updates status to FAILED on unhandled errors.

    Args:
        redis_client: Redis connection (for compatibility)
        repo_config_id: The model repo config ID
        db: MongoDB database connection

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """

    def handler(status: str, error_message: str) -> None:
        try:
            repo_config_repo = ModelRepoConfigRepository(db)
            repo_config_repo.update_repository(
                repo_config_id,
                {
                    "status": ModelImportStatus.FAILED.value,
                    "error_message": error_message,
                },
            )
            publish_status(repo_config_id, "failed", error_message)
        except Exception as e:
            logger.warning(f"Failed to update repo config {repo_config_id}: {e}")

    return handler


def create_model_training_build_failure_handler(
    db, model_build_id: str
) -> Callable[[str, str], None]:
    """
    Create a failure handler for ModelTrainingBuild build-level tasks.
    Updates extraction status to FAILED when processing fails.

    Args:
        db: MongoDB database connection
        model_build_id: The model training build ID

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from app.entities.enums import ExtractionStatus
    from app.repositories.model_training_build import ModelTrainingBuildRepository

    def handler(status: str, error_message: str) -> None:
        try:
            model_build_repo = ModelTrainingBuildRepository(db)
            model_build_repo.update_one(
                model_build_id,
                {
                    "extraction_status": ExtractionStatus.FAILED.value,
                    "extraction_error": error_message[:500],
                },
            )
            logger.info(
                f"Marked ModelTrainingBuild {model_build_id[:8]} as FAILED: "
                f"{error_message[:100]}"
            )
        except Exception as e:
            logger.warning(f"Failed to mark ModelTrainingBuild {model_build_id[:8]} as FAILED: {e}")

    return handler


def create_batch_model_training_build_failure_handler(
    db, model_build_ids: List[str]
) -> Callable[[str, str], None]:
    """
    Create a failure handler for batch ModelTrainingBuild prediction tasks.
    Bulk updates prediction status to FAILED for multiple builds.

    Args:
        db: MongoDB database connection
        model_build_ids: List of model training build IDs

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from bson import ObjectId

    from app.entities.enums import ExtractionStatus
    from app.repositories.model_training_build import ModelTrainingBuildRepository

    def handler(status: str, error_message: str) -> None:
        try:
            model_build_repo = ModelTrainingBuildRepository(db)
            build_oids = [ObjectId(bid) for bid in model_build_ids if ObjectId.is_valid(bid)]

            if build_oids:
                model_build_repo.collection.update_many(
                    {"_id": {"$in": build_oids}},
                    {
                        "$set": {
                            "prediction_status": ExtractionStatus.FAILED.value,
                            "prediction_error": error_message[:500],
                        }
                    },
                )

            logger.info(
                f"Marked {len(build_oids)} builds as PREDICTION FAILED: " f"{error_message[:100]}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to mark batch prediction failed for {len(model_build_ids)} builds: {e}"
            )

    return handler

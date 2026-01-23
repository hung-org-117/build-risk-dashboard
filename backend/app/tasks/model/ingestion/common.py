"""
Common utilities for model ingestion tasks.
"""

import logging
from typing import Callable

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
    from app.entities.model_repo_config import ModelImportStatus
    from app.repositories.model_repo_config import ModelRepoConfigRepository
    from app.tasks.model_processing import publish_status

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


def create_model_import_build_failure_handler(db, build_id: str) -> Callable[[str, str], None]:
    """
    Create a failure handler for ModelImportBuild build-level tasks.
    Updates build status to FAILED when ingestion fails.

    Args:
        db: MongoDB database connection
        build_id: The model import build ID

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from app.entities.model_import_build import ModelImportBuildStatus
    from app.repositories.model_import_build import ModelImportBuildRepository

    def handler(status: str, error_message: str) -> None:
        try:
            repo = ModelImportBuildRepository(db)
            repo.update_one(
                build_id,
                {
                    "status": ModelImportBuildStatus.FAILED.value,
                    "ingestion_error": error_message[:500],
                },
            )
            logger.info(f"Marked ModelImportBuild {build_id[:8]} as FAILED: {error_message[:100]}")
        except Exception as e:
            logger.warning(f"Failed to mark ModelImportBuild {build_id[:8]} as FAILED: {e}")

    return handler

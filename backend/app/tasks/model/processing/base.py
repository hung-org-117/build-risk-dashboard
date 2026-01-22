"""
Model Pipeline Processing - Base Task Classes.

Provides specialized task classes for Model Pipeline processing operations.
"""

from typing import Callable, Optional

from app.tasks.base import ProcessingTask


class ModelProcessingTask(ProcessingTask):
    """
    Model Pipeline Processing Task.

    Handles failures for individual ModelTrainingBuilds and ModelRepoConfig.

    Failure handling hierarchy (priority order):
    1. model_build_id -> Mark specific build extraction as FAILED
    2. repo_config_id -> Mark ModelRepoConfig as FAILED (orchestrator-level)
    """

    abstract = True

    def get_entity_failure_handler(self, kwargs: dict) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide Model Processing specific failure handling.

        Priority order (most specific first):
        1. model_build_id -> Mark specific build extraction as FAILED
        2. repo_config_id -> Mark ModelRepoConfig as FAILED

        Returns None if no matching entity ID found.
        """
        from app.tasks.model.processing.common import (
            create_model_training_build_failure_handler,
            create_repo_config_failure_handler,
        )

        # Priority 1: Build-level failure (most specific)
        model_build_id = kwargs.get("model_build_id")
        if model_build_id:
            return create_model_training_build_failure_handler(self.db, model_build_id)

        # Priority 2: Orchestrator-level failure
        repo_config_id = kwargs.get("repo_config_id")
        if repo_config_id:
            return create_repo_config_failure_handler(self.redis, repo_config_id, self.db)

        # No matching entity
        return None


class ModelPredictionTask(ProcessingTask):
    """
    Model Prediction Task.

    Handles failures for a BATCH of ModelTrainingBuilds.

    Failure handling for batch prediction:
    - model_build_ids (list) -> Bulk mark multiple builds as PREDICTION FAILED
    """

    abstract = True

    def get_entity_failure_handler(self, kwargs: dict) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide batch prediction failure handling.

        Handles model_build_ids (list) for batch prediction failures.

        Returns None if no matching entity IDs found.
        """
        from app.tasks.model.processing.common import (
            create_batch_model_training_build_failure_handler,
        )

        # Batch prediction failure
        model_build_ids = kwargs.get("model_build_ids")
        if model_build_ids and isinstance(model_build_ids, list):
            return create_batch_model_training_build_failure_handler(self.db, model_build_ids)

        # No matching entity
        return None

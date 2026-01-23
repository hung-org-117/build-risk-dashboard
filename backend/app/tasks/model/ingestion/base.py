"""
Model Pipeline Ingestion - Base Task Classes.

Provides specialized task classes for Model Pipeline ingestion operations.
"""

from typing import Callable, Optional

from pymongo.database import Database

from app.tasks.base import IngestionTask


class ModelIngestionTask(IngestionTask):
    """
    Task for Model Pipeline ingestion operations.

    Provides failure handlers for ModelRepoConfig and ModelImportBuild entities.

    Failure handling hierarchy (priority order):
    1. model_import_build_id -> Mark specific build as FAILED
    2. repo_config_id -> Mark ModelRepoConfig as FAILED (orchestrator-level)
    """

    abstract = True

    def get_pipeline_type(self) -> str:
        return "model"

    def get_build_repository(self, db: Database):
        from app.repositories.model_import_build import ModelImportBuildRepository

        return ModelImportBuildRepository(db)

    def get_entity_failure_handler(self, kwargs: dict) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide Model Pipeline specific failure handling.

        Priority order (most specific first):
        1. model_import_build_id -> Mark specific build as FAILED
        2. repo_config_id -> Mark ModelRepoConfig as FAILED

        Returns None if no matching entity ID found.
        """
        from app.tasks.model.ingestion.common import (
            create_model_import_build_failure_handler,
            create_repo_config_failure_handler,
        )

        # Priority 1: Build-level failure (most specific)
        build_id = kwargs.get("model_import_build_id")
        if build_id:
            return create_model_import_build_failure_handler(self.db, build_id)

        # Priority 2: Orchestrator-level failure
        repo_config_id = kwargs.get("repo_config_id")
        if repo_config_id:
            return create_repo_config_failure_handler(self.redis, repo_config_id, self.db)

        # No matching entity
        return None

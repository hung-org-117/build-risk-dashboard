"""
Training Pipeline Ingestion - Base Task Classes.

Provides specialized task classes for Training Scenario ingestion operations.
"""

from typing import Callable, Optional

from pymongo.database import Database

from app.tasks.base import IngestionTask


class ScenarioIngestionTask(IngestionTask):
    """
    Task for Training Scenario ingestion operations.

    Provides failure handlers for TrainingScenario and TrainingIngestionBuild entities.

    Failure handling hierarchy (priority order):
    1. ingestion_build_id -> Mark specific build as FAILED
    2. scenario_id -> Mark TrainingScenario as FAILED (orchestrator-level)
    """

    abstract = True

    def get_pipeline_type(self) -> str:
        return "dataset"

    def get_build_repository(self, db: Database):
        from app.repositories.training_ingestion_build import (
            TrainingIngestionBuildRepository,
        )

        return TrainingIngestionBuildRepository(db)

    def get_entity_failure_handler(self, kwargs: dict) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide Training Scenario specific failure handling.

        Priority order (most specific first):
        1. ingestion_build_id -> Mark specific build as FAILED
        2. scenario_id -> Mark TrainingScenario as FAILED

        Returns None if no matching entity ID found.
        """
        from app.tasks.training.ingestion.common import (
            create_scenario_failure_handler,
            create_training_ingestion_build_failure_handler,
        )

        # Priority 1: Build-level failure (most specific)
        build_id = kwargs.get("ingestion_build_id")
        if build_id:
            return create_training_ingestion_build_failure_handler(self.db, build_id)

        # Priority 2: Orchestrator-level failure
        scenario_id = kwargs.get("scenario_id")
        if scenario_id:
            return create_scenario_failure_handler(self.redis, scenario_id, self.db)

        # No matching entity
        return None

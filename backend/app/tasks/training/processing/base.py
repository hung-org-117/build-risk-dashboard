"""
Training Pipeline Processing - Base Task Classes.

Provides specialized task classes for Training Scenario processing operations.
"""

from typing import Callable, Optional

from app.tasks.base import ProcessingTask


class ScenarioProcessingTask(ProcessingTask):
    """
    Training Scenario Processing Task.

    Handles failures for individual TrainingEnrichmentBuilds and TrainingScenario.

    Failure handling hierarchy (priority order):
    1. enrichment_build_id -> Mark specific build extraction as FAILED
    2. scenario_id -> Mark TrainingScenario as FAILED (orchestrator-level)
    """

    abstract = True

    def get_entity_failure_handler(self, kwargs: dict) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide Training Processing specific failure handling.

        Priority order (most specific first):
        1. enrichment_build_id -> Mark specific build extraction as FAILED
        2. scenario_id -> Mark TrainingScenario as FAILED

        Returns None if no matching entity ID found.
        """
        from app.tasks.training.processing.common import (
            create_scenario_failure_handler,
            create_training_enrichment_build_failure_handler,
        )

        # Priority 1: Build-level failure (most specific)
        enrichment_build_id = kwargs.get("enrichment_build_id")
        if enrichment_build_id:
            return create_training_enrichment_build_failure_handler(self.db, enrichment_build_id)

        # Priority 2: Orchestrator-level failure
        scenario_id = kwargs.get("scenario_id")
        if scenario_id:
            return create_scenario_failure_handler(self.redis, scenario_id, self.db)

        # No matching entity
        return None

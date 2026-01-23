"""
Training Pipeline - Ingestion Tasks (Phase 1) - Public API.

Tasks have been split into app.tasks.training.ingestion/ for maintainability:
- common.py: Shared utilities
- orchestrator.py: Entry point tasks
- aggregate.py: Chord callbacks
- reingest.py: Retry tasks

All tasks preserve their original Celery task names via `name=` parameter.
"""

# Re-export all tasks from submodules
from app.tasks.training.ingestion import (
    aggregate_scenario_ingestion,
    create_scenario_failure_handler,
    handle_scenario_chord_error,
    reingest_failed_builds,
    start_scenario_ingestion,
)
from app.tasks.training.ingestion.common import create_training_ingestion_build_failure_handler

__all__ = [
    # Tasks
    "start_scenario_ingestion",
    "aggregate_scenario_ingestion",
    "handle_scenario_chord_error",
    "reingest_failed_builds",
    # Helpers
    "create_scenario_failure_handler",
    "create_training_ingestion_build_failure_handler",
]

"""
Training Ingestion Tasks Package.

Provides public API for all training ingestion tasks:
- start_scenario_ingestion
- aggregate_scenario_ingestion
- handle_scenario_chord_error
- reingest_failed_builds
"""

from app.tasks.training.ingestion.aggregate import (
    aggregate_scenario_ingestion,
    handle_scenario_chord_error,
)
from app.tasks.training.ingestion.base import ScenarioIngestionTask
from app.tasks.training.ingestion.common import (
    create_scenario_failure_handler,
    find_matching_repos,
    resolve_filter_config,
)
from app.tasks.training.ingestion.orchestrator import (
    filter_builds_for_scenario,
    process_ingestion_builds,
    start_scenario_ingestion,
)
from app.tasks.training.ingestion.reingest import reingest_failed_builds

__all__ = [
    # Base Classes
    "ScenarioIngestionTask",
    # Tasks
    "start_scenario_ingestion",
    "aggregate_scenario_ingestion",
    "handle_scenario_chord_error",
    "reingest_failed_builds",
    # Helpers
    "create_scenario_failure_handler",
    "resolve_filter_config",
    "find_matching_repos",
    "filter_builds_for_scenario",
    "process_ingestion_builds",
]

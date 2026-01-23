"""
Model Ingestion Tasks - Split from model_ingestion.py for better maintainability.

Modules:
- base.py: Base task class (ModelIngestionTask)
- orchestrator.py: Entry point tasks (start_model_processing, ingest_model_builds)
- fetch.py: Build fetching tasks (fetch_builds_batch, fetch_builds_until_existing)
- dispatch.py: Ingestion dispatching (dispatch_ingestion, aggregate_*)
- reingest.py: Re-ingestion and webhook tasks
"""

from app.tasks.model.ingestion.base import ModelIngestionTask
from app.tasks.model.ingestion.common import create_repo_config_failure_handler
from app.tasks.model.ingestion.dispatch import (
    aggregate_model_ingestion_results,
    dispatch_ingestion,
    handle_ingestion_chord_error,
)
from app.tasks.model.ingestion.fetch import (
    aggregate_fetch_results,
    fetch_builds_batch,
    fetch_builds_until_existing,
    handle_fetch_chord_error,
)
from app.tasks.model.ingestion.orchestrator import (
    ingest_model_builds,
    start_model_processing,
)
from app.tasks.model.ingestion.reingest import (
    ingest_webhook_build,
    reingest_failed_builds,
)

__all__ = [
    # Base Classes
    "ModelIngestionTask",
    # Orchestrator
    "start_model_processing",
    "ingest_model_builds",
    # Fetch
    "fetch_builds_batch",
    "fetch_builds_until_existing",
    "aggregate_fetch_results",
    "handle_fetch_chord_error",
    # Dispatch
    "dispatch_ingestion",
    "aggregate_model_ingestion_results",
    "handle_ingestion_chord_error",
    # Reingest
    "reingest_failed_builds",
    "ingest_webhook_build",
    # Helpers
    "create_repo_config_failure_handler",
]

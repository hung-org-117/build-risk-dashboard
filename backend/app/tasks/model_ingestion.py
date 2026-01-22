"""
Model Ingestion Tasks - Public API.

Tasks have been split into app.tasks.model.ingestion/ for maintainability:
- orchestrator.py: Entry point tasks
- fetch.py: Build fetching tasks
- dispatch.py: Ingestion dispatching
- reingest.py: Re-ingestion and webhook tasks

All tasks preserve their original Celery task names via `name=` parameter.
"""

# Re-export all tasks from submodules
from app.tasks.model.ingestion import (
    aggregate_fetch_results,
    aggregate_model_ingestion_results,
    create_repo_config_failure_handler,
    dispatch_ingestion,
    fetch_builds_batch,
    fetch_builds_until_existing,
    handle_fetch_chord_error,
    handle_ingestion_chord_error,
    ingest_model_builds,
    ingest_webhook_build,
    reingest_failed_builds,
    start_model_processing,
)
from app.tasks.model.ingestion.common import create_model_import_build_failure_handler

__all__ = [
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
    "create_model_import_build_failure_handler",
]

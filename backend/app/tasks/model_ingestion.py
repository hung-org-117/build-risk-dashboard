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
    create_model_import_build_failure_handler,
    create_repo_config_failure_handler,
    dispatch_ingestion_batch,
    fetch_builds_page,
    fetch_builds_until_existing,
    fetch_webhook_build,
    handle_fetch_chord_error,
    handle_fetch_completion,
    handle_ingestion_chord_error,
    handle_ingestion_completion,
    orchestrate_model_ingestion,
    reingest_failures,
    start_model_ingestion_pipeline,
)

__all__ = [
    # Orchestrator
    "start_model_ingestion_pipeline",
    "orchestrate_model_ingestion",
    # Fetch
    "fetch_builds_page",
    "fetch_builds_until_existing",
    "handle_fetch_completion",
    "handle_fetch_chord_error",
    "fetch_webhook_build",
    # Dispatch
    "dispatch_ingestion_batch",
    "handle_ingestion_completion",
    "handle_ingestion_chord_error",
    # Reingest
    "reingest_failures",
    # Helpers
    "create_repo_config_failure_handler",
    "create_model_import_build_failure_handler",
]

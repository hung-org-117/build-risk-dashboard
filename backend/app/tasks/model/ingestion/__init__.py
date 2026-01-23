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
from app.tasks.model.ingestion.common import (
    create_model_import_build_failure_handler,
    create_repo_config_failure_handler,
)
from app.tasks.model.ingestion.dispatch import (
    dispatch_ingestion_batch,
    handle_ingestion_chord_error,
    handle_ingestion_completion,
)
from app.tasks.model.ingestion.fetch import (
    fetch_builds_page,
    fetch_builds_until_existing,
    fetch_webhook_build,
    handle_fetch_chord_error,
    handle_fetch_completion,
)
from app.tasks.model.ingestion.orchestrator import (
    orchestrate_model_ingestion,
    start_model_ingestion_pipeline,
)
from app.tasks.model.ingestion.reingest import (
    reingest_failures,
)

__all__ = [
    # Base Classes
    "ModelIngestionTask",
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

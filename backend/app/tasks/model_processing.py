"""
Model Processing Tasks - Public API.

Tasks have been split into app.tasks.model.processing/ for maintainability:
- common.py: Shared utilities
- orchestrator.py: Entry point tasks
- extraction.py: Feature extraction
- prediction.py: Prediction tasks
- retry.py: Retry tasks

All tasks preserve their original Celery task names via `name=` parameter.
"""

# Re-export all tasks from submodules
from app.tasks.model.processing import (
    create_repo_config_failure_handler,
    dispatch_build_processing,
    finalize_model_processing,
    finalize_prediction,
    handle_processing_chain_error,
    predict_batch,
    process_workflow_run,
    publish_status,
    retry_failed_builds,
    start_processing_phase,
)
from app.tasks.model.processing.common import (
    create_batch_model_training_build_failure_handler,
    create_model_training_build_failure_handler,
)

__all__ = [
    # Orchestrator
    "start_processing_phase",
    "dispatch_build_processing",
    # Extraction
    "process_workflow_run",
    # Prediction
    "finalize_model_processing",
    "finalize_prediction",
    "predict_batch",
    "handle_processing_chain_error",
    # Retry
    "retry_failed_builds",
    # Helper
    "create_repo_config_failure_handler",
    "create_model_training_build_failure_handler",
    "create_batch_model_training_build_failure_handler",
    "publish_status",
]

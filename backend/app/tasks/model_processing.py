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
    dispatch_processing_batch,
    extract_build_features,
    handle_pipeline_completion,
    handle_prediction_completion,
    handle_processing_chain_error,
    predict_risk_batch,
    publish_status,
    retry_processing_failures,
    start_model_processing_pipeline,
)
from app.tasks.model.processing.common import (
    create_batch_model_training_build_failure_handler,
    create_model_training_build_failure_handler,
)

__all__ = [
    # Orchestrator
    "start_model_processing_pipeline",
    "dispatch_processing_batch",
    # Extraction
    "extract_build_features",
    # Prediction
    "handle_pipeline_completion",
    "handle_prediction_completion",
    "predict_risk_batch",
    "handle_processing_chain_error",
    # Retry
    "retry_processing_failures",
    # Helper
    "create_repo_config_failure_handler",
    "create_model_training_build_failure_handler",
    "create_batch_model_training_build_failure_handler",
    "publish_status",
]

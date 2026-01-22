"""
Model Processing Tasks - Split from model_processing.py for maintainability.

Modules:
- base.py: Base task classes (ModelProcessingTask, ModelPredictionTask)
- common.py: Shared utilities (failure handler)
- orchestrator.py: Entry point tasks (start_processing_phase, dispatch_build_processing)
- extraction.py: Feature extraction (process_workflow_run)
- prediction.py: Prediction tasks (finalize_model_processing, finalize_prediction)
- retry.py: Retry tasks (retry_failed_builds)
"""

from app.tasks.model.processing.base import ModelPredictionTask, ModelProcessingTask
from app.tasks.model.processing.common import (
    create_repo_config_failure_handler,
    publish_status,
)
from app.tasks.model.processing.extraction import process_workflow_run
from app.tasks.model.processing.orchestrator import (
    dispatch_build_processing,
    start_processing_phase,
)
from app.tasks.model.processing.prediction import (
    finalize_model_processing,
    finalize_prediction,
    handle_processing_chain_error,
    predict_batch,
)
from app.tasks.model.processing.retry import retry_failed_builds

__all__ = [
    # Base Classes
    "ModelProcessingTask",
    "ModelPredictionTask",
    # Common
    "create_repo_config_failure_handler",
    "publish_status",
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
]

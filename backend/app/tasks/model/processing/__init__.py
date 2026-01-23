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
from app.tasks.model.processing.extraction import extract_build_features
from app.tasks.model.processing.orchestrator import (
    dispatch_processing_batch,
    start_model_processing_pipeline,
)
from app.tasks.model.processing.prediction import (
    handle_pipeline_completion,
    handle_prediction_completion,
    handle_processing_chain_error,
    predict_risk_batch,
)
from app.tasks.model.processing.retry import retry_processing_failures

__all__ = [
    # Base Classes
    "ModelProcessingTask",
    "ModelPredictionTask",
    # Common
    "create_repo_config_failure_handler",
    "publish_status",
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
]

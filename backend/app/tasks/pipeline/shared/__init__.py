"""Shared pipeline definitions (data only)."""

from app.tasks.pipeline.shared.resources import (
    INGESTION_TASK_TO_CELERY,
    INPUT_REGISTRY,
    RESOURCE_LEAF_TASKS,
    TASK_DEPENDENCIES,
    FeatureResource,
    InputSpec,
    check_resource_availability,
    get_input_resource_names,
)

__all__ = [
    "FeatureResource",
    "InputSpec",
    "INPUT_REGISTRY",
    "TASK_DEPENDENCIES",
    "RESOURCE_LEAF_TASKS",
    "INGESTION_TASK_TO_CELERY",
    "check_resource_availability",
    "get_input_resource_names",
]

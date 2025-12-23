"""
Tracing Context - Thread-safe context management for distributed tracing.

This module provides a centralized way to manage tracing context across
Celery tasks and API requests. It uses Python's contextvars for thread-safety.

Usage:
    # Set context at the start of a task
    TracingContext.set(
        correlation_id="abc-123",
        dataset_id="dataset-456",
        pipeline_type="dataset_enrichment"
    )

    # Get context (automatically added to JSONFormatter logs)
    ctx = TracingContext.get()

    # Generate correlation_id prefix for manual logging
    prefix = TracingContext.get_log_prefix()  # "[corr=abc-123]"

    # Clear context at the end
    TracingContext.clear()
"""

import uuid
from contextvars import ContextVar
from typing import Dict

# Thread-safe context variables
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_dataset_id: ContextVar[str] = ContextVar("dataset_id", default="")
_version_id: ContextVar[str] = ContextVar("version_id", default="")
_repo_id: ContextVar[str] = ContextVar("repo_id", default="")
_pipeline_type: ContextVar[str] = ContextVar("pipeline_type", default="")
_task_name: ContextVar[str] = ContextVar("task_name", default="")


class TracingContext:
    """Thread-safe tracing context for distributed tracing."""

    @staticmethod
    def set(
        correlation_id: str = "",
        dataset_id: str = "",
        version_id: str = "",
        repo_id: str = "",
        pipeline_type: str = "",
        task_name: str = "",
    ) -> None:
        """Set tracing context for current execution."""
        if correlation_id:
            _correlation_id.set(correlation_id)
        if dataset_id:
            _dataset_id.set(dataset_id)
        if version_id:
            _version_id.set(version_id)
        if repo_id:
            _repo_id.set(repo_id)
        if pipeline_type:
            _pipeline_type.set(pipeline_type)
        if task_name:
            _task_name.set(task_name)

    @staticmethod
    def get() -> Dict[str, str]:
        """Get current tracing context as dict."""
        return {
            "correlation_id": _correlation_id.get(),
            "dataset_id": _dataset_id.get(),
            "version_id": _version_id.get(),
            "repo_id": _repo_id.get(),
            "pipeline_type": _pipeline_type.get(),
            "task_name": _task_name.get(),
        }

    @staticmethod
    def get_correlation_id() -> str:
        """Get current correlation ID."""
        return _correlation_id.get()

    @staticmethod
    def get_or_create_correlation_id() -> str:
        """Get current correlation ID or create a new one."""
        corr_id = _correlation_id.get()
        if not corr_id:
            corr_id = str(uuid.uuid4())
            _correlation_id.set(corr_id)
        return corr_id

    @staticmethod
    def get_log_prefix() -> str:
        """Get a formatted prefix for manual logging."""
        corr_id = _correlation_id.get()
        if corr_id:
            return f"[corr={corr_id[:8]}]"
        return ""

    @staticmethod
    def clear() -> None:
        """Clear all tracing context."""
        _correlation_id.set("")
        _dataset_id.set("")
        _version_id.set("")
        _repo_id.set("")
        _pipeline_type.set("")
        _task_name.set("")

    @staticmethod
    def copy() -> Dict[str, str]:
        """Copy current context for passing to child tasks."""
        return {
            "correlation_id": _correlation_id.get(),
            "dataset_id": _dataset_id.get(),
            "version_id": _version_id.get(),
            "repo_id": _repo_id.get(),
            "pipeline_type": _pipeline_type.get(),
        }


def get_correlation_id() -> str:
    """Convenience function to get current correlation ID."""
    return TracingContext.get_correlation_id()


def get_or_create_correlation_id() -> str:
    """Convenience function to get or create correlation ID."""
    return TracingContext.get_or_create_correlation_id()


def set_tracing_context(
    correlation_id: str = "",
    dataset_id: str = "",
    version_id: str = "",
    repo_id: str = "",
    pipeline_type: str = "",
) -> None:
    """Convenience function to set tracing context."""
    TracingContext.set(
        correlation_id=correlation_id,
        dataset_id=dataset_id,
        version_id=version_id,
        repo_id=repo_id,
        pipeline_type=pipeline_type,
    )

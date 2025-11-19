"""Custom exceptions for the ingestion pipeline."""
from __future__ import annotations


class PipelineError(Exception):
    """Base exception for pipeline failures."""


class PipelineConfigurationError(PipelineError):
    """Raised when required configuration is missing."""


class PipelineRateLimitError(PipelineError):
    """Raised when the upstream service enforces a rate limit."""
    def __init__(self, message: str, retry_after: int | float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class PipelineRetryableError(PipelineError):
    """Raised for transient issues where retrying later may succeed."""

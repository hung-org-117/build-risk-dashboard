"""Custom exceptions for the ingestion pipeline."""

from __future__ import annotations


class GithubError(Exception):
    """Base exception for pipeline failures."""


class GithubConfigurationError(GithubError):
    """Raised when required configuration is missing."""


class GithubRateLimitError(GithubError):
    """Raised when the upstream service enforces a rate limit."""

    def __init__(self, message: str, retry_after: int | float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class GithubRetryableError(GithubError):
    """Raised for transient issues where retrying later may succeed."""


class GithubAllRateLimitError(GithubError):
    """Raised when all GitHub tokens hit rate limits."""

    def __init__(self, message: str, retry_after: int | float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class GithubSecondaryRateLimitError(GithubRateLimitError):
    """
    Raised when GitHub's secondary rate limit (abuse detection) is triggered.

    Secondary rate limits are triggered by:
    - Too many requests in a short time window (burst)
    - Too many concurrent requests
    - Too many CPU-intensive requests

    These require longer backoff (typically 60s+) compared to primary rate limits.
    """

    pass


class LogUnavailableReason:
    """Reasons why job logs are unavailable."""

    PERMISSION_DENIED = "permission_denied"
    LOGS_EXPIRED = "logs_expired"
    JOB_NOT_FOUND = "job_not_found"
    RUN_IN_PROGRESS = "run_in_progress"
    RATE_LIMITED = "rate_limited"


class GithubLogsUnavailableError(GithubError):
    """
    Raised when job logs cannot be retrieved.

    This is a non-retryable error for cases like:
    - Permission denied (public repo without admin rights)
    - Logs expired (past retention period)
    - Job not found
    """

    def __init__(
        self,
        message: str,
        reason: str = LogUnavailableReason.PERMISSION_DENIED,
        job_id: int | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.job_id = job_id

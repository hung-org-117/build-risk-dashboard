"""
Base Celery Task with automatic TracingContext propagation and SafeTask pattern.

Task Hierarchy:
1. PipelineTask - Base with DB, Redis, TracingContext, rate limit handling
2. SafeTask - Adds run_safe() with error taxonomy, checkpoint/cleanup hooks, and on_failure

Specialized Task Classes (inherit from SafeTask):
  ├── IngestionTask (abstract)
  │     ├── ModelIngestionTask      - Handles model_import_build failures
  │     └── ScenarioIngestionTask   - Handles ingestion_build failures
  ├── ProcessingTask (abstract)
  │     ├── ModelProcessingTask     - Handles model_build extraction failures
  │     ├── ModelPredictionTask     - Handles batch prediction failures
  │     └── ScenarioProcessingTask  - Handles enrichment_build extraction failures
  ├── ScanTask                       - Handles scan record failures (Trivy/SonarQube)
  ├── ExportTask                     - Handles TrainingDatasetExport failures
  └── ModelExportTask                - Handles ExportJob failures

Error Taxonomy:
- TransientError: Retryable (network, timeout, API 429)
- PermanentError: Non-retryable (bad input, schema error)
- MissingResourceError: Expected missing (logs 404) - marks MISSING_RESOURCE

All tasks should catch SoftTimeLimitExceeded and convert to TransientError for retry.
"""

from __future__ import annotations

import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import redis
from celery import Task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from pymongo.database import Database

from app.config import settings
from app.core.tracing import TracingContext
from app.database.mongo import get_database
from app.services.github.exceptions import GithubAllRateLimitError, GithubRetryableError

logger = logging.getLogger(__name__)


# =============================================================================
# Error Taxonomy
# =============================================================================


class TransientError(Exception):
    """
    Retryable error: network glitch, timeout, API 429, temporary outage.

    SafeTask will checkpoint state, cleanup, and retry with exponential backoff.
    """


class PermanentError(Exception):
    """
    Non-retryable error: bad input, schema mismatch, deterministic failure.

    SafeTask will mark job as FAILED and NOT retry.
    """


class MissingResourceError(PermanentError):
    """
    Expected missing resource: logs expired (404), commit not found (squash merge).

    SafeTask will mark as MISSING_RESOURCE (not FAILED) - no retry needed.
    This is different from PermanentError because it's expected, not an error.
    """


# =============================================================================
# Task State for Checkpointing
# =============================================================================


@dataclass
class TaskState:
    """
    State for checkpoint/resume pattern.

    Tasks can use this to track progress through phases and resume after retry.
    """

    phase: str = "START"
    meta: dict[str, Any] = field(default_factory=dict)


# Heartbeat for Long-Running Tasks
class Heartbeat:
    """
    Periodic status updater for long-running tasks.

    Publishes heartbeat updates at regular intervals to indicate task is still
    running. Useful for monitoring and debugging stuck/slow tasks.

    Usage:
        def my_callback(elapsed_seconds: float) -> None:
            logger.info(f"Task still running ({elapsed_seconds:.1f}s)")

        with Heartbeat(callback=my_callback, interval_seconds=30):
            do_long_running_work()
    """

    def __init__(
        self,
        callback: Callable[[float], None],
        interval_seconds: float = 30.0,
    ) -> None:
        """
        Initialize heartbeat.

        Args:
            callback: Function called each interval with elapsed time in seconds
            interval_seconds: Time between heartbeats (default 30s)
        """
        self._callback = callback
        self._interval = interval_seconds
        self._timer: threading.Timer | None = None
        self._start_time: float | None = None
        self._stopped = threading.Event()

    def _tick(self) -> None:
        """Internal tick - call callback and schedule next tick."""
        if self._stopped.is_set():
            return

        import time

        elapsed = time.time() - (self._start_time or time.time())
        try:
            self._callback(elapsed)
        except Exception as e:
            logger.warning(f"Heartbeat callback error: {e}")

        # Schedule next tick
        if not self._stopped.is_set():
            self._timer = threading.Timer(self._interval, self._tick)
            self._timer.daemon = True
            self._timer.start()

    def start(self) -> None:
        """Start heartbeat timer."""
        import time

        self._start_time = time.time()
        self._stopped.clear()
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def stop(self) -> None:
        """Stop heartbeat timer."""
        self._stopped.set()
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def __enter__(self) -> "Heartbeat":
        """Context manager entry - start heartbeat."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stop heartbeat."""
        self.stop()


# Distributed Lock for Concurrency Control
class DistributedLock:
    """
    Redis-based distributed lock for critical sections.

    Prevents concurrent execution of protected code across multiple workers.
    Uses Redis SET NX with TTL to prevent deadlocks.

    Supports two modes:
    - **Non-blocking** (default): Retry a few times then fail fast
    - **Blocking**: Wait up to blocking_timeout for lock to become available

    Usage:
        lock = DistributedLock(redis_client, "export:scenario_123")
        with lock:
            generate_export_files()

        lock = DistributedLock(
            redis_client, "clone:repo_123",
            ttl_seconds=700,
            blocking=True,
            blocking_timeout=60,
        )
        with lock:
            clone_repository()

    Args:
        redis_client: Redis connection instance
        key: Lock key (should be unique per resource)
        ttl_seconds: Lock expiration time (default: 300s / 5 minutes)
        blocking: If True, use blocking mode (wait for lock). Default: False
        blocking_timeout: Max seconds to wait in blocking mode (default: 30)
        retry_times: Number of acquire retries in non-blocking mode (default: 3)
        retry_delay: Delay between retries in seconds (default: 1)
    """

    def __init__(
        self,
        redis_client,
        key: str,
        ttl_seconds: int = 300,
        blocking: bool = False,
        blocking_timeout: int = 30,
        retry_times: int = 3,
        retry_delay: float = 1.0,
    ):
        self._redis = redis_client
        self._key = f"lock:{key}"
        self._ttl = ttl_seconds
        self._blocking = blocking
        self._blocking_timeout = blocking_timeout
        self._retry_times = retry_times
        self._retry_delay = retry_delay
        self._lock_value: str | None = None
        self._native_lock = None  # For blocking mode

    def acquire(self) -> bool:
        """
        Attempt to acquire the lock.

        In blocking mode: Use redis-py's native Lock with blocking.
        In non-blocking mode: Retry a few times then return False.

        Returns True if lock was acquired, False otherwise.
        """
        import time
        import uuid

        self._lock_value = str(uuid.uuid4())

        if self._blocking:
            # Blocking mode: Use redis-py's native lock mechanism
            self._native_lock = self._redis.lock(
                self._key,
                timeout=self._ttl,
                blocking_timeout=self._blocking_timeout,
            )
            acquired = self._native_lock.acquire(blocking=True)
            if acquired:
                logger.debug(f"Lock acquired (blocking): {self._key}")
            else:
                logger.warning(
                    f"Failed to acquire lock (timeout={self._blocking_timeout}s): "
                    f"{self._key}"
                )
            return acquired

        # Non-blocking mode: Manual SET NX with retries
        for attempt in range(self._retry_times):
            acquired = self._redis.set(
                self._key,
                self._lock_value,
                nx=True,
                ex=self._ttl,
            )

            if acquired:
                logger.debug(f"Lock acquired: {self._key}")
                return True

            if attempt < self._retry_times - 1:
                time.sleep(self._retry_delay)

        logger.warning(
            f"Failed to acquire lock after {self._retry_times} attempts: {self._key}"
        )
        return False

    def release(self) -> bool:
        """
        Release the lock if we own it.

        In blocking mode: Use redis-py's native Lock release.
        In non-blocking mode: Use Lua script for atomic check-and-delete.
        """
        # Blocking mode: delegate to native lock
        if self._blocking and self._native_lock:
            try:
                self._native_lock.release()
                logger.debug(f"Lock released (blocking): {self._key}")
                return True
            except Exception as e:
                logger.warning(f"Failed to release lock {self._key}: {e}")
                return False

        # Non-blocking mode: Lua script atomic release
        if not self._lock_value:
            return False

        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        try:
            result = self._redis.eval(lua_script, 1, self._key, self._lock_value)
            if result:
                logger.debug(f"Lock released: {self._key}")
                return True
            else:
                logger.warning(f"Lock not owned or expired: {self._key}")
                return False
        except Exception as e:
            logger.warning(f"Failed to release lock {self._key}: {e}")
            return False

    def __enter__(self) -> "DistributedLock":
        """Context manager entry - acquire lock or raise."""
        if not self.acquire():
            raise RuntimeError(f"Failed to acquire distributed lock: {self._key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - always release lock."""
        self.release()

    @property
    def is_locked(self) -> bool:
        """Check if lock is currently held (by anyone)."""
        return self._redis.exists(self._key) == 1


def compute_backoff(
    attempt: int,
    *,
    base: int = 5,
    cap: int = 300,
    jitter: bool = True,
) -> int:
    """
    Compute exponential backoff with jitter.

    Args:
        attempt: Current retry attempt (0-indexed)
        base: Base delay in seconds
        cap: Maximum delay in seconds
        jitter: Add randomness to prevent thundering herd

    Returns:
        Delay in seconds
    """
    delay = min(cap, base * (2**attempt))
    if jitter:
        delay = int(delay * (0.7 + 0.6 * random.random()))  # 0.7x..1.3x
    return max(1, delay)


class PipelineTask(Task):
    """
    Base task with automatic database connection and TracingContext propagation.

    Provides:
    - Database connection (self.db)
    - Redis connection (self.redis)
    - TracingContext restoration from kwargs
    - GithubAllRateLimitError handling with exact countdown
    """

    abstract = True
    autoretry_for = (GithubRetryableError,)
    retry_backoff = True
    retry_backoff_max = 3600  # 1 hour max
    retry_kwargs = {"max_retries": 3}
    default_retry_delay = 10

    def __init__(self) -> None:
        self._db: Database | None = None
        self._redis: redis.Redis | None = None

    def __call__(self, *args, **kwargs):
        """Handle GithubAllRateLimitError with exact countdown."""
        try:
            return super().__call__(*args, **kwargs)
        except GithubAllRateLimitError as exc:
            countdown = self._calculate_countdown(exc)
            if countdown:
                logger.warning(
                    f"All tokens exhausted for {self.name}, retrying in {countdown}s"
                )
                raise self.retry(exc=exc, countdown=countdown) from exc
            else:
                raise self.retry(exc=exc, countdown=self.default_retry_delay) from exc

    def _calculate_countdown(self, exc: GithubAllRateLimitError) -> Optional[int]:
        """Calculate countdown from retry_after."""
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is None:
            return None
        if isinstance(retry_after, (int, float)):
            return max(1, int(retry_after) + 5)
        elif isinstance(retry_after, datetime):
            now = datetime.now(timezone.utc)
            delta = (retry_after - now).total_seconds()
            return max(1, int(delta) + 5)
        return None

    def before_start(self, task_id: str, args: tuple, kwargs: dict):
        """Restore TracingContext from kwargs."""
        correlation_id = kwargs.get("correlation_id", "")
        scenario_id = kwargs.get("scenario_id", "")
        source_id = kwargs.get("source_id", "")
        repo_id = kwargs.get("repo_id", "") or kwargs.get("repo_config_id", "")
        task_short_name = self.name.split(".")[-1] if self.name else ""

        if correlation_id:
            TracingContext.set(
                correlation_id=correlation_id,
                scenario_id=scenario_id,
                source_id=source_id,
                repo_id=repo_id,
                task_name=task_short_name,
            )

    def after_return(
        self, status: str, retval: Any, task_id: str, args: tuple, kwargs: dict, einfo
    ):
        """Clear database and TracingContext after completion."""
        if self._db is not None:
            self._db = None
        TracingContext.clear()
        if self._redis:
            self._redis.close()
            self._redis = None

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = get_database()
        return self._db

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo
    ):
        """Log failure and notify for rate limit exhaustion."""
        logger.error("Task %s failed: %s", self.name, exc, exc_info=exc)
        if isinstance(exc, GithubAllRateLimitError):
            self._notify_rate_limit_exhausted(exc)

    def _notify_rate_limit_exhausted(self, exc: GithubAllRateLimitError) -> None:
        """Send notification when all GitHub tokens exhausted."""
        try:
            from app.services.notification_service import NotificationService

            notification_service = NotificationService(self.db)
            retry_after = exc.retry_after
            if isinstance(retry_after, (int, float)):
                retry_after = datetime.fromtimestamp(retry_after, tz=timezone.utc)
            notification_service.notify_rate_limit_exhausted(
                retry_after=retry_after,
                task_name=self.name,
            )
        except Exception as notify_exc:
            logger.warning(f"Failed to send rate limit notification: {notify_exc}")


# =============================================================================
# SafeTask - Task with run_safe() Pattern
# =============================================================================


class SafeTask(PipelineTask):
    """
    Task with standardized error handling via run_safe().

    Behavior:
    - SoftTimeLimitExceeded: checkpoint + cleanup + retry
    - TransientError: checkpoint + cleanup + retry (exponential backoff)
    - Retry: re-raise (avoid double-handle)
    - MissingResourceError: mark MISSING_RESOURCE + cleanup + raise (no retry)
    - PermanentError: mark FAILED + cleanup + raise (no retry)
    - Other Exception: mark FAILED + cleanup + raise (configurable)

    Usage:
        @celery_app.task(bind=True, base=SafeTask, ...)
        def my_task(self, job_id: str, ...):
            def _work(state: TaskState) -> dict:
                if state.phase == "START":
                    # do work
                    state.phase = "DONE"
                return {"result": "ok"}

            return self.run_safe(
                job_id=job_id,
                work=_work,
                save_state_fn=lambda s: my_repo.save_state(job_id, s),
                mark_failed_fn=lambda e: my_repo.mark_failed(job_id, str(e)),
                cleanup_fn=lambda s: cleanup_partial_work(job_id, s),
            )
    """

    abstract = True

    # Disable Celery's autoretry - run_safe() handles retry logic
    # This prevents conflict where Celery auto-retries before run_safe() can checkpoint
    autoretry_for = ()

    max_retries = 3
    soft_retry_delay = 15
    transient_retry_base = 5
    transient_retry_cap = 300

    def get_entity_failure_handler(
        self, kwargs: dict
    ) -> Optional[Callable[[str, str], None]]:
        """
        Return failure handler for entity-level failures.

        Base implementation (no default handlers):
        - Subclasses override to provide specific entity failure handling
        - ScanTask, ExportTask, ModelExportTask provide their own implementations
        - IngestionTask/ProcessingTask subclasses handle entity-specific failures

        Returns None if no matching entity ID found.

        Subclass Examples:
        - ModelIngestionTask: handles model_import_build_id, repo_config_id
        - ScenarioIngestionTask: handles ingestion_build_id, scenario_id
        - ModelProcessingTask: handles model_build_id, repo_config_id
        - ScenarioProcessingTask: handles enrichment_build_id, scenario_id
        """
        # Default: no orchestrator handling
        # Each subclass is responsible for implementing its own
        return None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure by calling entity failure handler if defined."""
        super().on_failure(exc, task_id, args, kwargs, einfo)

        handler = self.get_entity_failure_handler(kwargs)
        if handler:
            handler("failed", str(exc))

    def run_safe(
        self,
        job_id: str,
        work: Callable[[TaskState], Any],
        *,
        load_state_fn: Callable[[str], TaskState] | None = None,
        save_state_fn: Callable[[TaskState], None] | None = None,
        mark_failed_fn: Callable[[Exception], None] | None = None,
        mark_missing_fn: Callable[[Exception], None] | None = None,
        cleanup_fn: Callable[[TaskState], None] | None = None,
        fail_on_unknown: bool = True,
    ) -> Any:
        """
        Execute work with standardized error handling.

        Args:
            job_id: Unique identifier for logging/tracing
            work: Work function that takes TaskState and returns result
            load_state_fn: Optional fn to load TaskState from DB
            save_state_fn: Optional fn to save TaskState to DB
            mark_failed_fn: Optional fn to mark job as FAILED in DB
            mark_missing_fn: Optional fn to mark job as MISSING_RESOURCE in DB
            cleanup_fn: Optional fn to cleanup partial work (MUST be idempotent)
            fail_on_unknown: If True, unknown exceptions mark FAILED. If False, retry.

        Returns:
            Result from work function
        """
        task_name = self.name or self.__class__.__name__
        log_prefix = f"[{task_name}][{job_id[:8] if len(job_id) >= 8 else job_id}]"

        # Load or create state
        state = load_state_fn(job_id) if load_state_fn else TaskState()

        try:
            result = work(state)
            if save_state_fn:
                save_state_fn(state)
            return result

        except SoftTimeLimitExceeded as e:
            return self._handle_timeout(
                e, state, log_prefix, save_state_fn, mark_failed_fn, cleanup_fn
            )

        except TransientError as e:
            return self._handle_transient(
                e, state, log_prefix, save_state_fn, mark_failed_fn, cleanup_fn
            )

        except TransientError as e:
            # Transient - use unified retryable error handler
            self._handle_retryable_error(
                exc=e,
                state=state,
                log_prefix=log_prefix,
                error_type=f"TransientError, phase={state.phase}",
                save_state_fn=save_state_fn,
                mark_failed_fn=mark_failed_fn,
                cleanup_fn=cleanup_fn,
                delay_fn=lambda attempt: compute_backoff(
                    attempt,
                    base=self.transient_retry_base,
                    cap=self.transient_retry_cap,
                ),
            )

        except Retry:
            # Celery internal - re-raise
            raise

        except MissingResourceError as e:
            # Expected missing - mark MISSING_RESOURCE, no retry
            logger.warning(
                f"{log_prefix} MissingResourceError, phase={state.phase}: {e}"
            )
            if mark_missing_fn:
                try:
                    mark_missing_fn(e)
                except Exception as mark_exc:
                    logger.warning(f"{log_prefix} Failed to mark missing: {mark_exc}")
            if cleanup_fn:
                self._safe_cleanup(cleanup_fn, state, log_prefix)
            raise

        except PermanentError as e:
            # Permanent - mark FAILED, no retry
            logger.error(f"{log_prefix} PermanentError, phase={state.phase}: {e}")
            if mark_failed_fn:
                try:
                    mark_failed_fn(e)
                except Exception as mark_exc:
                    logger.warning(f"{log_prefix} Failed to mark failed: {mark_exc}")
            if cleanup_fn:
                self._safe_cleanup(cleanup_fn, state, log_prefix)
            raise

        except GithubAllRateLimitError as e:
            # All tokens exhausted - checkpoint and re-raise
            # PipelineTask handles retry with proper countdown
            logger.warning(
                f"{log_prefix} All GitHub tokens rate limited, will retry: {e}"
            )
            self._checkpoint_and_cleanup(save_state_fn, cleanup_fn, state, log_prefix)
            raise

        except GithubRetryableError as e:
            # GitHub API transient error - use unified retryable error handler
            self._handle_retryable_error(
                exc=e,
                state=state,
                log_prefix=log_prefix,
                error_type="GithubRetryableError",
                save_state_fn=save_state_fn,
                mark_failed_fn=mark_failed_fn,
                cleanup_fn=cleanup_fn,
                delay_fn=lambda attempt: compute_backoff(
                    attempt,
                    base=self.transient_retry_base,
                    cap=self.transient_retry_cap,
                ),
            )

        except Exception as e:
            # Unknown exception
            logger.exception(f"{log_prefix} Unexpected error, phase={state.phase}")
            if fail_on_unknown:
                # Treat as permanent
                self._mark_and_cleanup(mark_failed_fn, cleanup_fn, state, log_prefix, e)
                raise
            else:
                # Treat as transient - use unified retryable error handler
                self._handle_retryable_error(
                    exc=e,
                    state=state,
                    log_prefix=log_prefix,
                    error_type="UnknownError (treating as transient)",
                    save_state_fn=save_state_fn,
                    mark_failed_fn=mark_failed_fn,
                    cleanup_fn=cleanup_fn,
                    delay_fn=lambda attempt: compute_backoff(
                        attempt,
                        base=self.transient_retry_base,
                        cap=self.transient_retry_cap,
                    ),
                )

    def _safe_cleanup(
        self,
        cleanup_fn: Callable[[TaskState], None] | None,
        state: TaskState,
        log_prefix: str,
    ) -> None:
        """Execute cleanup safely, catching any exceptions."""
        if cleanup_fn:
            try:
                cleanup_fn(state)
            except Exception as cleanup_exc:
                logger.warning(f"{log_prefix} Cleanup failed: {cleanup_exc}")

    def _mark_and_cleanup(
        self,
        mark_fn: Callable[[Exception], None] | None,
        cleanup_fn: Callable[[TaskState], None] | None,
        state: TaskState,
        log_prefix: str,
        exc: Exception,
    ) -> None:
        """Call mark_failed_fn and cleanup_fn safely."""
        if mark_fn:
            try:
                mark_fn(exc)
            except Exception as mark_exc:
                logger.warning(f"{log_prefix} Failed to mark failed: {mark_exc}")
        if cleanup_fn:
            self._safe_cleanup(cleanup_fn, state, log_prefix)

    def _checkpoint_and_cleanup(
        self,
        save_state_fn: Callable[[TaskState], None] | None,
        cleanup_fn: Callable[[TaskState], None] | None,
        state: TaskState,
        log_prefix: str,
    ) -> None:
        """Checkpoint state and cleanup before retry."""
        if save_state_fn:
            save_state_fn(state)
        if cleanup_fn:
            self._safe_cleanup(cleanup_fn, state, log_prefix)

    def _handle_retryable_error(
        self,
        exc: Exception,
        state: TaskState,
        log_prefix: str,
        error_type: str,
        save_state_fn: Callable[[TaskState], None] | None,
        mark_failed_fn: Callable[[Exception], None] | None,
        cleanup_fn: Callable[[TaskState], None] | None,
        delay_fn: Callable[[int], int],
    ) -> None:
        """
        Unified handler for retryable errors.

        Args:
            exc: The exception that was raised
            state: Current task state
            log_prefix: Logging prefix
            error_type: Human-readable error type for logging
            save_state_fn: Function to checkpoint state
            mark_failed_fn: Function to mark job as failed
            cleanup_fn: Function to cleanup partial work
            delay_fn: Function(attempt) -> delay_seconds
        """
        attempt = getattr(self.request, "retries", 0)

        if self.max_retries == 0 or attempt >= self.max_retries:
            logger.error(f"{log_prefix} {error_type}, no retries left: {exc}")
            self._mark_and_cleanup(mark_failed_fn, cleanup_fn, state, log_prefix, exc)
            raise exc

        delay = delay_fn(attempt)
        logger.info(f"{log_prefix} {error_type}, retry in {delay}s: {exc}")
        self._checkpoint_and_cleanup(save_state_fn, cleanup_fn, state, log_prefix)
        raise self.retry(countdown=delay, exc=exc)


# =============================================================================
# ScanTask - Task with Entity Failure Handler for Scans
# =============================================================================


class ScanTask(SafeTask):
    """
    Task for scan operations (Trivy, SonarQube) with entity failure handling.

    When a scan task exhausts all retries (e.g., due to SoftTimeLimitExceeded),
    this class ensures the scan entity is properly marked as FAILED instead of
    being stuck at SCANNING status.

    Usage:
        @celery_app.task(bind=True, base=ScanTask, ...)
        def my_scan_task(self, scenario_id: str, commit_sha: str, ...):
            ...

    The task must pass scenario_id and commit_sha as kwargs for failure handling.
    """

    abstract = True

    def get_entity_failure_handler(
        self, kwargs: dict
    ) -> Optional[Callable[[str, str], None]]:
        """
        Override to provide scan-specific failure handling.

        Extracts scenario_id, commit_sha, and tool_type from kwargs
        and returns a handler that marks the scan as failed.
        """
        scenario_id = kwargs.get("scenario_id")
        commit_sha = kwargs.get("commit_sha")
        tool_type = kwargs.get("tool_type", self._detect_tool_type())

        if not scenario_id or not commit_sha:
            return None

        return self._create_scan_failure_handler(scenario_id, commit_sha, tool_type)

    def _detect_tool_type(self) -> str:
        """Detect tool type from task name."""
        task_name = self.name or ""
        if "trivy" in task_name.lower():
            return "trivy"
        elif "sonar" in task_name.lower():
            return "sonarqube"
        return "unknown"

    def _create_scan_failure_handler(
        self, scenario_id: str, commit_sha: str, tool_type: str
    ) -> Callable[[str, str], None]:
        """
        Create a failure handler that marks scan record as FAILED.

        Args:
            scenario_id: Scenario ID
            commit_sha: Commit SHA being scanned
            tool_type: "trivy" or "sonarqube"

        Returns:
            Handler function(status, error_message) -> None
        """

        def update_scan_failed(status: str, error_message: str) -> None:
            try:
                from bson import ObjectId

                from app.database.mongo import get_database

                db = get_database()
                scenario_obj_id = ObjectId(scenario_id)

                # Mark scan as failed in the appropriate repository
                if tool_type == "trivy":
                    from app.repositories.trivy_commit_scan import (
                        TrivyCommitScanRepository,
                    )

                    scan_repo = TrivyCommitScanRepository(db)
                    scan = scan_repo.find_by_scenario_and_commit(
                        scenario_obj_id, commit_sha
                    )
                    if scan and scan.id:
                        scan_repo.mark_failed(scan.id, error_message)
                        logger.info(
                            f"Marked Trivy scan {scan.id} as FAILED: {error_message[:100]}"
                        )
                elif tool_type == "sonarqube":
                    from app.repositories.sonar_commit_scan import (
                        SonarCommitScanRepository,
                    )

                    scan_repo = SonarCommitScanRepository(db)
                    scan = scan_repo.find_by_scenario_and_commit(
                        scenario_obj_id, commit_sha
                    )
                    if scan and scan.id:
                        scan_repo.mark_failed(scan.id, error_message)
                        logger.info(
                            f"Marked SonarQube scan {scan.id} as FAILED: {error_message[:100]}"
                        )

            except Exception as e:
                logger.warning(
                    f"Failed to mark {tool_type} scan as failed for "
                    f"{scenario_id[:8]}/{commit_sha[:8]}: {e}"
                )

        return update_scan_failed


# =============================================================================
# IngestionTask - Base Task for Ingestion Operations
# =============================================================================


class IngestionTask(SafeTask):
    """
    Base task for ingestion operations with build-level failure handling.

    When ingestion tasks fail (SoftTimeLimitExceeded, network errors, etc.),
    this class ensures the affected builds are properly marked as FAILED.

    Subclasses must implement:
    - get_pipeline_type() -> Literal["model", "dataset"]
    - get_build_repository(db) -> Repository for build entities

    Usage:
        @celery_app.task(bind=True, base=IngestionTask, ...)
        def my_ingestion_task(self, pipeline_id: str, pipeline_type: str, ...):
            ...
    """

    abstract = True

    def get_pipeline_type(self) -> str:
        """Return pipeline type: 'model' or 'dataset'."""
        raise NotImplementedError("Subclass must implement get_pipeline_type()")

    def get_build_repository(self, db: Database):
        """Return the appropriate build repository for this pipeline."""
        raise NotImplementedError("Subclass must implement get_build_repository()")

    def mark_builds_failed_by_commits(
        self,
        pipeline_id: str,
        pipeline_type: str,
        commit_shas: list[str],
        error_message: str,
    ) -> int:
        """
        Mark builds as FAILED based on commit SHAs.

        Args:
            pipeline_id: ModelRepoConfig ID or TrainingScenario ID
            pipeline_type: "model" or "dataset"
            commit_shas: List of commit SHAs whose builds should be marked
            error_message: Error message to store

        Returns:
            Number of builds marked as failed
        """
        try:
            if pipeline_type == "model":
                from app.repositories.model_import_build import (
                    ModelImportBuildRepository,
                )

                repo = ModelImportBuildRepository(self.db)
                return repo.mark_builds_failed_by_commits(
                    pipeline_id, commit_shas, error_message
                )
            else:
                from app.repositories.training_ingestion_build import (
                    TrainingIngestionBuildRepository,
                )

                repo = TrainingIngestionBuildRepository(self.db)
                return repo.mark_builds_failed_by_commits(
                    pipeline_id, commit_shas, error_message
                )
        except Exception as e:
            logger.warning(f"Failed to mark builds as failed: {e}")
            return 0

    def mark_all_ingesting_failed(
        self,
        pipeline_id: str,
        pipeline_type: str,
        error_message: str,
    ) -> int:
        """
        Mark ALL currently INGESTING builds as FAILED.

        Used when a repo-wide failure occurs (e.g., clone failed).

        Args:
            pipeline_id: ModelRepoConfig ID or TrainingScenario ID
            pipeline_type: "model" or "dataset"
            error_message: Error message to store

        Returns:
            Number of builds marked as failed
        """
        try:
            if pipeline_type == "model":
                from app.repositories.model_import_build import (
                    ModelImportBuildRepository,
                )

                repo = ModelImportBuildRepository(self.db)
                return repo.mark_all_ingesting_failed(pipeline_id, error_message)
            else:
                from app.repositories.training_ingestion_build import (
                    TrainingIngestionBuildRepository,
                )

                repo = TrainingIngestionBuildRepository(self.db)
                return repo.mark_all_ingesting_failed(pipeline_id, error_message)
        except Exception as e:
            logger.warning(f"Failed to mark all ingesting builds as failed: {e}")
            return 0


# Specialized Ingestion Task Classes
# These classes have been moved to their respective modules for better organization.
# Import from:
# - from app.tasks.model.ingestion.base import ModelIngestionTask
# - from app.tasks.training.ingestion.base import ScenarioIngestionTask


# =============================================================================
# ProcessingTask - Base Task for Processing Operations
# =============================================================================


class ProcessingTask(SafeTask):
    """
    Base task for feature extraction/processing operations with build-level failure handling.
    """

    abstract = True


# Specialized Processing Task Classes
# These classes have been moved to their respective modules for better organization.
# Import from:
# - from app.tasks.model.processing.base import ModelProcessingTask, ModelPredictionTask
# - from app.tasks.training.processing.base import ScenarioProcessingTask


# Export Tasks
class ExportTask(SafeTask):
    """
    Training Scenario Export Task.

    Handles failures for TrainingDatasetExport entities.
    """

    abstract = True

    def get_entity_failure_handler(
        self, kwargs: dict
    ) -> Optional[Callable[[str, str], None]]:
        """Override to handle export_id."""
        export_id = kwargs.get("export_id")
        if export_id:
            return self._create_export_failure_handler(export_id)

        return super().get_entity_failure_handler(kwargs)

    def _create_export_failure_handler(
        self, export_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for TrainingDatasetExport."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.training_dataset_export import ExportStatus
                from app.repositories.training_dataset_export import (
                    TrainingDatasetExportRepository,
                )

                db = get_database()
                export_repo = TrainingDatasetExportRepository(db)

                export_repo.update_one(
                    export_id,
                    {
                        "status": ExportStatus.FAILED.value,
                        "error_message": error_message[:500],
                    },
                )

                logger.info(
                    f"Marked TrainingDatasetExport {export_id[:8]} as FAILED: {error_message[:100]}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to mark TrainingDatasetExport {export_id[:8]} as FAILED: {e}"
                )

        return update_failed


class ModelExportTask(SafeTask):
    """
    Model Pipeline Export Task.

    Handles failures for ExportJob entities.
    """

    abstract = True

    def get_entity_failure_handler(
        self, kwargs: dict
    ) -> Optional[Callable[[str, str], None]]:
        """Override to handle job_id."""
        job_id = kwargs.get("job_id")
        if job_id:
            return self._create_export_job_failure_handler(job_id)

        return super().get_entity_failure_handler(kwargs)

    def _create_export_job_failure_handler(
        self, job_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for ExportJob."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.export_job import ExportStatus
                from app.repositories.export_job import ExportJobRepository

                db = get_database()
                job_repo = ExportJobRepository(db)

                job_repo.update_status(
                    job_id,
                    ExportStatus.FAILED.value,
                    error_message=error_message[:500],
                )

                logger.info(
                    f"Marked ExportJob {job_id[:8]} as FAILED: {error_message[:100]}"
                )
            except Exception as e:
                logger.warning(f"Failed to mark ExportJob {job_id[:8]} as FAILED: {e}")

        return update_failed

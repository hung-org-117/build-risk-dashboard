"""
Base Celery Task with automatic TracingContext propagation and SafeTask pattern.

Task Hierarchy:
1. PipelineTask - Base with DB, Redis, TracingContext, rate limit handling
2. SafeTask - Adds run_safe() with error taxonomy and checkpoint/cleanup hooks

Error Taxonomy:
- TransientError: Retryable (network, timeout, API 429)
- PermanentError: Non-retryable (bad input, schema error)
- MissingResourceError: Expected missing (logs 404) - marks MISSING_RESOURCE

All tasks should catch SoftTimeLimitExceeded and convert to TransientError for retry.
"""

from __future__ import annotations

import logging
import random
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
from app.services.github.exceptions import (
    GithubAllRateLimitError,
    GithubRetryableError,
)

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


# =============================================================================
# Backoff Helper
# =============================================================================


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


# =============================================================================
# PipelineTask - Base Task
# =============================================================================


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

    max_retries = 5
    soft_retry_delay = 15
    transient_retry_base = 5
    transient_retry_cap = 300

    def get_entity_failure_handler(
        self, kwargs: dict
    ) -> Optional[Callable[[str, str], None]]:
        """
        Auto-detect entity type from kwargs and return appropriate failure handler.

        Checks for these keys in priority order (more specific first):
        1. Build-level IDs (most granular):
           - enrichment_build_id → TrainingEnrichmentBuild
           - ingestion_build_id → TrainingIngestionBuild
        2. Parent-level IDs:
           - repo_config_id → ModelRepoConfig
           - scenario_id → TrainingScenario (but not if also has commit_sha → ScanTask)
           - export_id → TrainingDatasetExport

        Returns a callable(status: str, error_message: str) -> None
        that updates the relevant entity to FAILED status.
        """
        # Skip if this is a ScanTask (handled by ScanTask subclass)
        if kwargs.get("commit_sha") and kwargs.get("scenario_id"):
            # Likely a scan task - let ScanTask handle it
            return None

        # === BUILD-LEVEL HANDLERS (most granular - check first) ===

        # Check for TrainingEnrichmentBuild (feature extraction)
        enrichment_build_id = kwargs.get("enrichment_build_id")
        if enrichment_build_id:
            return self._create_enrichment_build_failure_handler(enrichment_build_id)

        # Check for TrainingIngestionBuild (ingestion)
        # ingestion_build_id = kwargs.get("ingestion_build_id")
        # if ingestion_build_id:
        #     return self._create_ingestion_build_failure_handler(ingestion_build_id)

        # === PARENT-LEVEL HANDLERS ===

        # Check for ModelRepoConfig (Model Pipeline)
        repo_config_id = kwargs.get("repo_config_id")
        if repo_config_id:
            return self._create_model_repo_config_failure_handler(repo_config_id)

        # Check for TrainingScenario (Training Pipeline)
        scenario_id = kwargs.get("scenario_id")
        if scenario_id:
            return self._create_training_scenario_failure_handler(scenario_id)

        # Check for TrainingDatasetExport (Export)
        export_id = kwargs.get("export_id")
        if export_id:
            return self._create_training_export_failure_handler(export_id)

        return None

    def _create_enrichment_build_failure_handler(
        self, enrichment_build_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for TrainingEnrichmentBuild (feature extraction)."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.enums import ExtractionStatus
                from app.repositories.training_enrichment_build import (
                    TrainingEnrichmentBuildRepository,
                )

                db = get_database()
                repo = TrainingEnrichmentBuildRepository(db)
                repo.update_extraction_status(
                    enrichment_build_id,
                    ExtractionStatus.FAILED,
                    error_message=error_message[:500],
                )
                logger.info(
                    f"Marked TrainingEnrichmentBuild {enrichment_build_id[:8]} as FAILED: "
                    f"{error_message[:100]}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to mark TrainingEnrichmentBuild {enrichment_build_id[:8]} as FAILED: {e}"
                )

        return update_failed

    def _create_ingestion_build_failure_handler(
        self, ingestion_build_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for TrainingIngestionBuild (ingestion)."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.training_ingestion_build import IngestionStatus
                from app.repositories.training_ingestion_build import (
                    TrainingIngestionBuildRepository,
                )

                db = get_database()
                repo = TrainingIngestionBuildRepository(db)
                repo.update_one(
                    ingestion_build_id,
                    {
                        "status": IngestionStatus.FAILED.value,
                        "ingestion_error": error_message[:500],
                    },
                )
                logger.info(
                    f"Marked TrainingIngestionBuild {ingestion_build_id[:8]} as FAILED: "
                    f"{error_message[:100]}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to mark TrainingIngestionBuild {ingestion_build_id[:8]} as FAILED: {e}"
                )

        return update_failed

    def _create_model_repo_config_failure_handler(
        self, repo_config_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for ModelRepoConfig."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.model_repo_config import ModelImportStatus
                from app.repositories.model_repo_config import ModelRepoConfigRepository
                from app.tasks.shared.events import publish_model_repo_updated

                db = get_database()
                repo = ModelRepoConfigRepository(db)
                repo.update_one(
                    repo_config_id,
                    {
                        "status": ModelImportStatus.FAILED.value,
                        "error_message": error_message[:500],
                    },
                )
                publish_model_repo_updated(
                    repo_config_id, ModelImportStatus.FAILED.value, error=error_message
                )
                logger.info(
                    f"Marked ModelRepoConfig {repo_config_id[:8]} as FAILED: {error_message[:100]}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to mark ModelRepoConfig {repo_config_id[:8]} as FAILED: {e}"
                )

        return update_failed

    def _create_training_scenario_failure_handler(
        self, scenario_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for TrainingScenario."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.training_scenario import ScenarioStatus
                from app.repositories.training_scenario import (
                    TrainingScenarioRepository,
                )
                from app.tasks.shared.events import publish_scenario_updated

                db = get_database()
                repo = TrainingScenarioRepository(db)
                repo.update_one(
                    scenario_id,
                    {
                        "status": ScenarioStatus.FAILED.value,
                        "error_message": error_message[:500],
                    },
                )
                publish_scenario_updated(
                    scenario_id, ScenarioStatus.FAILED.value, error=error_message
                )
                logger.info(
                    f"Marked TrainingScenario {scenario_id[:8]} as FAILED: {error_message[:100]}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to mark TrainingScenario {scenario_id[:8]} as FAILED: {e}"
                )

        return update_failed

    def _create_training_export_failure_handler(
        self, export_id: str
    ) -> Callable[[str, str], None]:
        """Create failure handler for TrainingDatasetExport."""

        def update_failed(status: str, error_message: str) -> None:
            try:
                from app.database.mongo import get_database
                from app.entities.training_dataset_export import ExportStatus
                from app.repositories.training_export import TrainingExportRepository

                db = get_database()
                repo = TrainingExportRepository(db)
                repo.update_one(
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
        if load_state_fn:
            state = load_state_fn(job_id)
        else:
            state = TaskState()

        try:
            result = work(state)
            # Success - optionally save final state
            if save_state_fn:
                save_state_fn(state)
            return result

        except SoftTimeLimitExceeded as e:
            # Timeout - checkpoint, cleanup, retry
            logger.warning(
                f"{log_prefix} Soft time limit exceeded, phase={state.phase}"
            )
            if save_state_fn:
                save_state_fn(state)
            if cleanup_fn:
                self._safe_cleanup(cleanup_fn, state, log_prefix)
            raise self.retry(countdown=self.soft_retry_delay, exc=e)

        except TransientError as e:
            # Transient - checkpoint, cleanup, retry with backoff
            attempt = getattr(self.request, "retries", 0)
            delay = compute_backoff(
                attempt, base=self.transient_retry_base, cap=self.transient_retry_cap
            )
            logger.info(
                f"{log_prefix} TransientError, phase={state.phase}, retry in {delay}s: {e}"
            )
            if save_state_fn:
                save_state_fn(state)
            if cleanup_fn:
                self._safe_cleanup(cleanup_fn, state, log_prefix)
            raise self.retry(countdown=delay, exc=e)

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

        except Exception as e:
            # Unknown exception
            logger.exception(f"{log_prefix} Unexpected error, phase={state.phase}")
            if fail_on_unknown:
                # Treat as permanent
                if mark_failed_fn:
                    try:
                        mark_failed_fn(e)
                    except Exception as mark_exc:
                        logger.warning(
                            f"{log_prefix} Failed to mark failed: {mark_exc}"
                        )
                if cleanup_fn:
                    self._safe_cleanup(cleanup_fn, state, log_prefix)
                raise
            else:
                # Treat as transient - retry
                attempt = getattr(self.request, "retries", 0)
                delay = compute_backoff(
                    attempt,
                    base=self.transient_retry_base,
                    cap=self.transient_retry_cap,
                )
                if save_state_fn:
                    save_state_fn(state)
                if cleanup_fn:
                    self._safe_cleanup(cleanup_fn, state, log_prefix)
                raise self.retry(countdown=delay, exc=e)

    def _safe_cleanup(
        self, cleanup_fn: Callable[[TaskState], None], state: TaskState, log_prefix: str
    ) -> None:
        """Execute cleanup safely, catching any exceptions."""
        try:
            cleanup_fn(state)
        except Exception as cleanup_exc:
            logger.warning(f"{log_prefix} Cleanup failed: {cleanup_exc}")


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
                from app.database.mongo import get_database
                from app.tasks.shared.events import publish_scenario_scan_updated
                from app.tasks.shared.scan_context_helpers import (
                    check_and_mark_scans_completed,
                    increment_scan_failed,
                )

                db = get_database()

                # Mark scan as failed in the appropriate repository
                if tool_type == "trivy":
                    from app.repositories.trivy_commit_scan import (
                        TrivyCommitScanRepository,
                    )

                    scan_repo = TrivyCommitScanRepository(db)
                    scan = scan_repo.find_by_scenario_and_commit(
                        scenario_id, commit_sha
                    )
                    if scan:
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
                        scenario_id, commit_sha
                    )
                    if scan:
                        scan_repo.mark_failed(scan.id, error_message)
                        logger.info(
                            f"Marked SonarQube scan {scan.id} as FAILED: {error_message[:100]}"
                        )

                # Publish event and update counters
                publish_scenario_scan_updated(
                    scenario_id=scenario_id,
                    scan_id="",  # May not have scan_id at this point
                    commit_sha=commit_sha,
                    tool_type=tool_type,
                    status="failed",
                    error=error_message,
                )

                increment_scan_failed(db, scenario_id)
                check_and_mark_scans_completed(db, scenario_id)

            except Exception as e:
                logger.warning(
                    f"Failed to mark {tool_type} scan as failed for "
                    f"{scenario_id[:8]}/{commit_sha[:8]}: {e}"
                )

        return update_scan_failed

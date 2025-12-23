"""
Pipeline Run Entity - Tracks complete pipeline execution history.

This entity provides high-level tracking for entire pipeline runs,
linking to FeatureAuditLog records for per-build details via correlation_id.

Collection: pipeline_runs
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class PipelineType(str, Enum):
    """Type of pipeline being executed."""

    DATASET_VALIDATION = "dataset_validation"
    DATASET_ENRICHMENT = "dataset_enrichment"
    MODEL_INGESTION = "model_ingestion"
    MODEL_PROCESSING = "model_processing"


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Completed with some failures
    FAILED = "failed"
    CANCELLED = "cancelled"


class PhaseStatus(str, Enum):
    """Individual phase status within a pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PhaseResult(BaseEntity):
    """Result of a single phase within the pipeline."""

    phase_name: str  # e.g., "clone", "worktree", "logs", "validation", "processing"
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Counts
    total_items: int = 0  # Total repos/builds to process
    processed_items: int = 0  # Successfully processed
    failed_items: int = 0  # Failed items
    skipped_items: int = 0  # Skipped items

    # Error tracking
    errors: List[str] = Field(default_factory=list)

    # Phase-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        use_enum_values = True


class PipelineRun(BaseEntity):
    """
    Track a complete pipeline execution from start to finish.

    This is the HIGH-LEVEL tracking entity that provides:
    - Overall pipeline status and duration
    - Phase-by-phase progress (ingestion, processing, etc.)
    - Link to detailed FeatureAuditLog records via correlation_id

    Collection: pipeline_runs
    """

    class Config:
        collection = "pipeline_runs"
        use_enum_values = True

    # === Unique Identifier ===
    correlation_id: str = Field(
        ...,
        description="UUID linking all tasks/logs in this pipeline run",
    )

    # === Pipeline Type ===
    pipeline_type: PipelineType = Field(
        ...,
        description="Type of pipeline: dataset_validation, dataset_enrichment, etc.",
    )

    # === Source Entity References (one will be populated based on type) ===
    dataset_id: Optional[PyObjectId] = Field(None, description="For dataset_validation pipeline")
    version_id: Optional[PyObjectId] = Field(None, description="For dataset_enrichment pipeline")
    repo_config_id: Optional[PyObjectId] = Field(
        None, description="For model_ingestion/model_processing pipeline"
    )

    # === Execution Status ===
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # === Progress Tracking ===
    total_repos: int = 0
    processed_repos: int = 0
    total_builds: int = 0
    processed_builds: int = 0
    failed_builds: int = 0

    # === Phase Results ===
    phases: List[PhaseResult] = Field(default_factory=list)

    # === Final Summary ===
    result_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Final aggregated results (features extracted, errors, etc.)",
    )

    # === Error Tracking ===
    error_message: Optional[str] = None

    # === Audit Info ===
    triggered_by: Optional[str] = Field(None, description="User ID or 'system' for automated runs")
    request_id: Optional[str] = Field(None, description="Original API X-Request-ID")

    # === Helper Methods ===
    def start(self) -> PipelineRun:
        """Mark pipeline as started."""
        self.status = PipelineStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        return self

    def complete(self, summary: Optional[Dict[str, Any]] = None) -> PipelineRun:  # noqa: F821
        """Mark pipeline as completed."""
        self.status = PipelineStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        if summary:
            self.result_summary = summary
        return self

    def complete_partial(self, summary: Optional[Dict[str, Any]] = None) -> PipelineRun:
        """Mark pipeline as completed with some failures."""
        self.status = PipelineStatus.PARTIAL
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        if summary:
            self.result_summary = summary
        return self

    def fail(self, error: str) -> PipelineRun:
        """Mark pipeline as failed."""
        self.status = PipelineStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.error_message = error
        return self

    def cancel(self) -> PipelineRun:
        """Mark pipeline as cancelled."""
        self.status = PipelineStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        return self

    def get_phase(self, phase_name: str) -> Optional[PhaseResult]:
        """Get a phase by name."""
        for phase in self.phases:
            if phase.phase_name == phase_name:
                return phase
        return None

    def start_phase(self, phase_name: str, total_items: int = 0) -> PhaseResult:
        """Start a new phase or update existing one."""
        phase = self.get_phase(phase_name)
        if phase:
            phase.status = PhaseStatus.RUNNING
            phase.started_at = datetime.now(timezone.utc)
            if total_items:
                phase.total_items = total_items
        else:
            phase = PhaseResult(
                phase_name=phase_name,
                status=PhaseStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                total_items=total_items,
            )
            self.phases.append(phase)
        return phase

    def complete_phase(
        self,
        phase_name: str,
        processed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[PhaseResult]:
        """Complete a phase with results."""
        phase = self.get_phase(phase_name)
        if phase:
            phase.status = PhaseStatus.COMPLETED
            phase.completed_at = datetime.now(timezone.utc)
            if phase.started_at:
                phase.duration_seconds = (phase.completed_at - phase.started_at).total_seconds()
            phase.processed_items = processed
            phase.failed_items = failed
            phase.skipped_items = skipped
            if metadata:
                phase.metadata = metadata
        return phase

    def fail_phase(self, phase_name: str, error: str) -> Optional[PhaseResult]:
        """Mark a phase as failed."""
        phase = self.get_phase(phase_name)
        if phase:
            phase.status = PhaseStatus.FAILED
            phase.completed_at = datetime.now(timezone.utc)
            if phase.started_at:
                phase.duration_seconds = (phase.completed_at - phase.started_at).total_seconds()
            phase.errors.append(error)
        return phase

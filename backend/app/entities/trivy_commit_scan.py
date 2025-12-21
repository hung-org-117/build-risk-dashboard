"""
TrivyCommitScan Entity - Tracks Trivy scans per commit in a version.

Used for tracking scan status and retry functionality.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class TrivyScanStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


class TrivyCommitScan(BaseEntity):
    """
    Tracks Trivy scan status per commit in a dataset version.

    Flow:
    1. dispatch_scan_for_commit creates this with status=pending
    2. start_trivy_scan_for_version_commit updates to scanning
    3. On completion, updates to completed with metrics
    4. On failure, updates to failed with error_message

    Allows retry functionality with updated config.
    """

    # Version and commit reference
    dataset_version_id: PyObjectId = Field(..., description="DatasetVersion ID")
    commit_sha: str = Field(..., description="Git commit SHA")
    repo_full_name: str = Field(..., description="Repository full name (owner/repo)")

    # Status tracking
    status: TrivyScanStatus = TrivyScanStatus.PENDING
    error_message: Optional[str] = None

    # Scan configuration (for retry with updated config)
    scan_config: Optional[Dict] = Field(
        None,
        description="Trivy config: severity, scanners, extraArgs",
    )
    selected_metrics: Optional[list] = Field(
        None,
        description="Selected metrics to filter",
    )

    # Results
    metrics: Optional[Dict] = Field(
        None,
        description="Scan metrics results",
    )
    builds_affected: int = Field(
        0,
        description="Number of builds backfilled with results",
    )

    # Path info for retry
    worktree_path: Optional[str] = None

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Retry tracking
    retry_count: int = 0

    class Config:
        collection = "trivy_commit_scans"

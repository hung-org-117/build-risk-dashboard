"""
SonarScanPending Entity - Tracks pending SonarQube scans.

Used for async scanning pattern during enrichment where:
1. Enrichment starts scan and returns immediately
2. SonarQube processes analysis asynchronously
3. Webhook updates features when scan completes
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class ScanPendingStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


class SonarScanPending(BaseEntity):
    """
    Tracks pending SonarQube scans initiated during enrichment.

    Flow:
    1. dispatch_scan_for_commit creates this record with status=pending
    2. Celery task runs sonar-scanner on worktree, status=scanning
    3. SonarQube webhook triggers when analysis completes
    4. Webhook handler fetches metrics and backfills to builds
    """

    # Version and commit reference
    dataset_version_id: PyObjectId = Field(
        ...,
        description="DatasetVersion ID for filtering scan metrics",
    )
    commit_sha: str = Field(..., description="Git commit SHA")
    repo_full_name: str = Field(
        ...,
        description="Repository full name (owner/repo)",
    )

    # SonarQube identifiers
    component_key: str = Field(
        ...,
        description="SonarQube project/component key (format: {version_id}_{repo}_{commit})",
    )
    repo_url: str

    # Scan configuration (for retry with updated config)
    scan_config: Optional[Dict] = Field(
        None,
        description="SonarQube config: projectKey, extraProperties",
    )

    # Status tracking
    status: ScanPendingStatus = ScanPendingStatus.PENDING
    error_message: Optional[str] = None

    # Results (populated on completion)
    metrics: Optional[Dict] = None
    builds_affected: int = Field(
        0,
        description="Number of builds backfilled with results",
    )

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Retry tracking
    retry_count: int = 0

    class Config:
        collection = "sonar_scan_pending"

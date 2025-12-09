"""
SonarScanPending Entity - Tracks pending SonarQube scans.

Used for async scanning pattern where:
1. Pipeline starts scan and returns immediately
2. Webhook updates features when scan completes
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Literal, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class ScanPendingStatus(str, Enum):
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


class SonarScanPending(BaseEntity):
    """
    Tracks pending SonarQube scans initiated by the pipeline.

    When a pipeline runs with sonar_* features:
    1. SonarMeasuresNode creates this record with status=scanning
    2. Celery task runs sonar-scanner
    3. SonarQube webhook triggers when done
    4. Webhook handler fetches metrics and updates the build
    """

    # Build reference (can be ModelBuild or EnrichmentBuild)
    build_id: PyObjectId
    build_type: Literal["model", "enrichment"]

    # SonarQube identifiers
    component_key: str = Field(..., description="SonarQube project/component key")
    commit_sha: str
    repo_url: str

    # Status tracking
    status: ScanPendingStatus = ScanPendingStatus.SCANNING
    error_message: Optional[str] = None

    # Results (populated on completion)
    metrics: Optional[Dict] = None

    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    class Config:
        collection = "sonar_scan_pending"

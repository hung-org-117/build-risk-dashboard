"""DTOs for Build API - RawBuildRun as primary source with optional training enrichment."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BuildSummary(BaseModel):
    """
    Summary of a CI build from ModelTrainingBuild with RawBuildRun enrichment.

    Primary data comes from ModelTrainingBuild (builds that have been processed).
    Additional data (conclusion, branch, etc.) comes from RawBuildRun.
    """

    # Identity - using RawBuildRun._id as primary key
    id: str = Field(..., alias="_id")

    # From RawBuildRun - always available after ingestion
    build_number: Optional[int] = None
    build_id: str = ""  # CI provider's build ID (e.g., GitHub run ID)
    conclusion: str = "unknown"  # success, failure, cancelled, etc.
    commit_sha: str = ""
    branch: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    web_url: Optional[str] = None

    # Logs info from RawBuildRun
    logs_available: Optional[bool] = None
    logs_expired: bool = False

    # Training data from ModelTrainingBuild (always present since we query from training builds)
    has_training_data: bool = False
    training_build_id: Optional[str] = None
    extraction_status: Optional[str] = None  # pending, completed, failed, partial
    feature_count: int = 0
    extraction_error: Optional[str] = None
    missing_resources: List[str] = []

    class Config:
        populate_by_name = True


class BuildDetail(BaseModel):
    """
    Detailed view of a build with full RawBuildRun data and training features.
    """

    # Identity
    id: str = Field(..., alias="_id")

    # From RawBuildRun
    build_number: Optional[int] = None
    build_id: str = ""
    conclusion: str = "unknown"
    commit_sha: str = ""
    branch: str = ""
    commit_message: Optional[str] = None
    commit_author: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    web_url: Optional[str] = None
    provider: str = "github_actions"

    # Logs
    logs_available: Optional[bool] = None
    logs_expired: bool = False

    # Training enrichment
    has_training_data: bool = False
    training_build_id: Optional[str] = None
    extraction_status: Optional[str] = None
    feature_count: int = 0
    extraction_error: Optional[str] = None
    features: Dict[str, Any] = {}

    class Config:
        populate_by_name = True


class BuildListResponse(BaseModel):
    """Paginated list of builds."""

    items: List[BuildSummary]
    total: int
    page: int
    size: int

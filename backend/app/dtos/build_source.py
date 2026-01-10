"""DTOs for BuildSource - CSV upload and validation for training data."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.entities.build_source import (
    ValidationStatus,
    SourceMapping,
    ValidationStats,
)


class BuildSourceCreate(BaseModel):
    """Create a new build source via CSV upload."""

    name: str = Field(..., min_length=1)
    description: Optional[str] = None


class BuildSourceUpdate(BaseModel):
    """Update build source (typically for column mapping)."""

    name: Optional[str] = None
    description: Optional[str] = None
    mapped_fields: Optional[SourceMapping] = None
    ci_provider: Optional[str] = None  # e.g., "github_actions"


class BuildSourceResponse(BaseModel):
    """Build source response."""

    id: str
    name: str
    description: Optional[str]

    # Upload info
    file_name: Optional[str]
    rows: int
    size_bytes: int
    columns: List[str]
    mapped_fields: SourceMapping
    preview: List[Dict[str, Any]]

    # CI Provider
    ci_provider: Optional[str]

    # Validation status
    validation_status: ValidationStatus
    validation_progress: int
    validation_stats: ValidationStats
    validation_error: Optional[str]

    # Timestamps
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    validation_started_at: Optional[datetime]
    validation_completed_at: Optional[datetime]

    # Setup step
    setup_step: int


class BuildSourceListResponse(BaseModel):
    """Paginated list of build sources."""

    items: List[BuildSourceResponse]
    total: int
    skip: int
    limit: int


class SourceBuildResponse(BaseModel):
    """Individual build from a source."""

    id: str
    source_id: str
    build_id_from_source: str
    repo_name_from_source: str
    status: str
    validation_error: Optional[str]
    validated_at: Optional[datetime]
    raw_repo_id: Optional[str]
    raw_run_id: Optional[str]


class SourceRepoStatsResponse(BaseModel):
    """Repository stats for a source."""

    id: str
    source_id: str
    raw_repo_id: str
    full_name: str
    ci_provider: str
    builds_total: int
    builds_found: int
    builds_not_found: int
    builds_filtered: int
    is_valid: bool
    validation_error: Optional[str]

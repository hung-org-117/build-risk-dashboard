"""
BuildSource Entity - Represents a data collection source for builds.

This entity tracks sources of build data (CSV uploads, imports, etc.)
that populate RawRepository and RawBuildRun tables.

Key design principles:
- Source tracking: Tracks origin of build data
- Validation: Manages validation process for the source
- Provider-agnostic: Supports multiple CI providers
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.ci_providers.models import CIProvider

from .base import BaseEntity, PyObjectId


class ValidationStatus(str, Enum):
    """Validation status for a build source."""

    PENDING = "pending"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceMapping(BaseModel):
    """Mappings from source columns to required build identifiers."""

    build_id: Optional[str] = None
    repo_name: Optional[str] = None
    ci_provider: Optional[str] = (
        None  # Column name for CI provider (multi-provider mode)
    )


class ValidationStats(BaseModel):
    """Statistics from source validation process."""

    repos_total: int = 0
    repos_valid: int = 0
    repos_invalid: int = 0
    repos_not_found: int = 0
    builds_total: int = 0
    builds_found: int = 0
    builds_not_found: int = 0
    builds_filtered: int = 0


class BuildSource(BaseEntity):
    """
    Represents a data collection source for builds.

    Sources can be CSV uploads, model pipeline imports, or other future sources.
    Each source populates RawRepository and RawBuildRun tables during validation.
    """

    class Config:
        collection = "build_sources"
        use_enum_values = True

    user_id: Optional[PyObjectId] = None
    name: str
    description: Optional[str] = None

    # CSV upload fields
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    rows: int = 0
    size_bytes: int = 0
    columns: List[str] = Field(default_factory=list)
    mapped_fields: SourceMapping = Field(default_factory=SourceMapping)
    preview: List[Dict[str, Any]] = Field(default_factory=list)

    # CI Provider configuration
    ci_provider: Optional[CIProvider] = Field(
        default=CIProvider.GITHUB_ACTIONS,
        description="CI provider for the source (None if using column mapping)",
    )

    # Validation status
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_task_id: Optional[str] = None
    validation_started_at: Optional[datetime] = None
    validation_completed_at: Optional[datetime] = None
    validation_progress: int = 0  # 0-100
    validation_stats: ValidationStats = Field(default_factory=ValidationStats)
    validation_error: Optional[str] = None

    # Setup progress tracking (1=uploaded, 2=validated)
    setup_step: int = 1

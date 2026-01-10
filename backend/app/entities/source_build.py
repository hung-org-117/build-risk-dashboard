"""
SourceBuild Entity - Tracks builds from a BuildSource during validation.

Links builds from CSV rows to their validated state.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId


class SourceBuildStatus(str, Enum):
    """Status of a build during source validation."""

    PENDING = "pending"
    FOUND = "found"
    NOT_FOUND = "not_found"
    FILTERED = "filtered"  # Excluded by build filters (bot, cancelled, etc.)
    ERROR = "error"


class SourceBuild(BaseEntity):
    """
    Tracks a build from a BuildSource during validation.

    Created when CSV is uploaded, updated during validation.
    Links to RawRepository and RawBuildRun after validation.
    """

    class Config:
        collection = "source_builds"
        use_enum_values = True

    # Source reference
    source_id: PyObjectId = Field(
        ...,
        description="Reference to build_sources",
    )

    # From CSV/source
    build_id_from_source: str = Field(
        ...,
        description="Build ID as provided in source (CSV column)",
    )
    repo_name_from_source: str = Field(
        ...,
        description="Repository name as provided in source",
    )

    # Validation status
    status: SourceBuildStatus = SourceBuildStatus.PENDING
    validation_error: Optional[str] = None
    validated_at: Optional[datetime] = None

    # Raw data references (populated after validation)
    raw_repo_id: Optional[PyObjectId] = Field(
        None,
        description="Reference to raw_repositories table",
    )
    raw_run_id: Optional[PyObjectId] = Field(
        None,
        description="Reference to raw_build_runs table",
    )

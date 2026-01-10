"""
SourceRepoStats Entity - Per-repository stats for a BuildSource.

Tracks validation statistics per repository during source validation.
"""

from typing import Optional

from pydantic import Field

from app.ci_providers.models import CIProvider
from app.entities.base import BaseEntity, PyObjectId


class SourceRepoStats(BaseEntity):
    """Per-repository stats for a BuildSource. Stored in separate collection."""

    class Config:
        collection = "source_repo_stats"
        use_enum_values = True

    # References
    source_id: PyObjectId = Field(
        ...,
        description="Reference to build_sources",
    )
    raw_repo_id: PyObjectId = Field(
        ...,
        description="Reference to raw_repositories",
    )

    # Repo info (denormalized for convenience)
    full_name: str

    # CI Provider config
    ci_provider: CIProvider = Field(default=CIProvider.GITHUB_ACTIONS)

    # Validation stats
    builds_total: int = 0
    builds_found: int = 0
    builds_not_found: int = 0
    builds_filtered: int = 0
    is_valid: bool = True
    validation_error: Optional[str] = None

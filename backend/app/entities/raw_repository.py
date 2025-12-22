"""
RawRepository Entity - Immutable GitHub repository data.

This entity stores raw repository information fetched from GitHub.
It serves as a single source of truth for repository metadata across all flows.
"""

from typing import Any, Dict, Optional

from pydantic import Field

from app.entities.base import BaseEntity


class RawRepository(BaseEntity):
    """
    Raw repository data from GitHub.

    This is the single source of truth for repository information.
    Multiple flows can reference the same repository via raw_repo_id.
    """

    class Config:
        collection = "raw_repositories"

    # Core identifiers
    full_name: str = Field(
        ...,
        description="Repository full name (owner/repo). Unique across GitHub.",
    )
    github_repo_id: int = Field(
        ...,
        description="GitHub's internal repository ID.",
    )

    default_branch: str = Field(
        default="main",
        description="Default branch name (main, master, develop, etc.)",
    )
    is_private: bool = Field(
        default=False,
        description="Whether the repository is private",
    )

    main_lang: Optional[str] = Field(
        None,
        description="Primary programming language (lowercase)",
    )

    # Full GitHub metadata (for future use)
    github_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete GitHub API response for this repository",
    )

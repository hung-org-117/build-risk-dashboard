"""
Repository Entity Resource Provider.

Provides the repository entity (ModelRepository/EnrichmentRepository)
as a resource for extract nodes and other providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from app.pipeline.resources import ResourceProvider, ResourceNames

if TYPE_CHECKING:
    from app.pipeline.core.context import ExecutionContext
    from app.entities.model_repository import ModelRepository
    from app.entities.enrichment_repository import EnrichmentRepository

RepoType = Union["ModelRepository", "EnrichmentRepository"]


class RepoEntityProvider(ResourceProvider):
    """
    Provides the repository entity.

    The repository is passed when creating the ExecutionContext
    and stored in _init_repo. This provider exposes it as a proper resource.
    """

    @property
    def name(self) -> str:
        return ResourceNames.REPO_ENTITY

    def initialize(self, context: "ExecutionContext") -> RepoType:
        """Return the repository entity from context initialization."""
        if context._init_repo is None:
            raise ValueError("Repository entity not provided to ExecutionContext")
        return context._init_repo

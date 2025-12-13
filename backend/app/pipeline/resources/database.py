"""
Database Resource Provider.

Provides the MongoDB database reference as a resource for providers
that need to access repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.pipeline.resources import ResourceProvider, ResourceNames

if TYPE_CHECKING:
    from app.pipeline.core.context import ExecutionContext


class DatabaseProvider(ResourceProvider):
    """
    Provides the MongoDB database reference.

    The database is passed when creating the ExecutionContext
    and stored in _init_db. This provider exposes it as a proper resource.
    """

    @property
    def name(self) -> str:
        return ResourceNames.DATABASE

    def initialize(self, context: "ExecutionContext") -> Any:
        """Return the database reference from context initialization."""
        if context._init_db is None:
            raise ValueError("Database reference not provided to ExecutionContext")
        return context._init_db

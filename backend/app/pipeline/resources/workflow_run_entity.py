"""
WorkflowRun Entity Resource Provider.

Provides the WorkflowRunRaw entity as a resource for extract nodes
and other providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.pipeline.resources import ResourceProvider, ResourceNames

if TYPE_CHECKING:
    from app.pipeline.core.context import ExecutionContext
    from app.entities.workflow_run import WorkflowRunRaw


class WorkflowRunProvider(ResourceProvider):
    """
    Provides the WorkflowRunRaw entity.

    The workflow run is passed when creating the ExecutionContext
    and stored in _init_workflow_run. This provider exposes it as a proper resource.
    """

    @property
    def name(self) -> str:
        return ResourceNames.WORKFLOW_RUN

    def initialize(self, context: "ExecutionContext") -> Optional["WorkflowRunRaw"]:
        """Return the workflow run entity from context initialization."""
        return context._init_workflow_run

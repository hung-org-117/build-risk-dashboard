from abc import ABC, abstractmethod
from typing import Any, Dict, TypeVar

T = TypeVar("T")


class PipelineContext:
    """
    Shared context passed between pipeline steps.
    Holds configuration, resources, and intermediate results.
    """

    def __init__(self, pipeline_id: str, config: Dict[str, Any]):
        self.pipeline_id = pipeline_id
        self.config = config
        self.resources: Dict[str, Any] = {}
        self.features: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.errors: list[Dict[str, Any]] = []
        self._should_stop = False

    def stop(self):
        """Signal the pipeline to stop execution."""
        self._should_stop = True

    @property
    def is_stopped(self) -> bool:
        return self._should_stop


class PipelineStep(ABC):
    """
    Abstract base class for a single step in the pipeline.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute the step logic.

        Args:
            context: The shared pipeline context.

        Returns:
            The updated pipeline context.
        """
        pass

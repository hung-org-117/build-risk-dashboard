"""
Resource Providers - Base class and interfaces for pipeline resources.

Resources are shared dependencies that feature nodes need:
- Git repository (cloned, with commit ensured)
- GitHub API client
- Build log storage
- Workflow run data
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from app.pipeline.core.context import ExecutionContext


class ResourceProvider(ABC):
    """
    Base class for resource providers.
    
    Resource providers are responsible for:
    1. Initializing expensive resources (git clone, API clients)
    2. Making them available in the execution context
    3. Cleaning up after pipeline execution
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this resource."""
        pass
    
    @abstractmethod
    def initialize(self, context: "ExecutionContext") -> Any:
        """
        Initialize the resource and return it.
        
        The returned value will be stored in context.resources[self.name]
        """
        pass
    
    def cleanup(self, context: "ExecutionContext") -> None:
        """
        Clean up the resource after pipeline execution.
        
        Override this to release resources like file handles, connections, etc.
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"


class ResourceManager:
    """
    Manages initialization and cleanup of all resources.
    """
    
    def __init__(self):
        self._providers: Dict[str, ResourceProvider] = {}
        self._logger = logging.getLogger(__name__)
    
    def register(self, provider: ResourceProvider) -> None:
        """Register a resource provider."""
        self._providers[provider.name] = provider

    def get_registered_names(self) -> Set[str]:
        """Return names of all registered providers."""
        return set(self._providers.keys())

    def initialize(
        self, 
        context: "ExecutionContext", 
        required_resources: Optional[Set[str]] = None,
    ) -> None:
        """
        Initialize only the resources that are required.

        Args:
            context: Execution context to attach resources to
            required_resources: Optional subset to initialize (defaults to all)
        """
        resource_names = (
            self.get_registered_names()
            if required_resources is None
            else required_resources
        )
        missing = [r for r in resource_names if r not in self._providers]

        if missing:
            self._logger.warning(
                "No provider registered for resources: %s", ", ".join(sorted(missing))
            )
        
        for name in resource_names:
            provider = self._providers.get(name)
            if not provider:
                continue

            # Skip if resource already exists on context
            if hasattr(context, "has_resource") and context.has_resource(name):
                continue

            try:
                resource = provider.initialize(context)
                context.set_resource(name, resource)
            except Exception as e:
                raise ResourceInitializationError(
                    f"Failed to initialize resource '{name}': {e}"
                ) from e
    
    def initialize_all(self, context: "ExecutionContext") -> None:
        """Initialize all registered resources."""
        self.initialize(context, self.get_registered_names())
    
    def cleanup_all(self, context: "ExecutionContext") -> None:
        """Cleanup all resources."""
        for name, provider in self._providers.items():
            try:
                provider.cleanup(context)
            except Exception as e:
                # Log but don't raise - we want to cleanup all resources
                import logging
                logging.getLogger(__name__).error(
                    f"Error cleaning up resource '{name}': {e}"
                )


class ResourceInitializationError(Exception):
    """Raised when a resource fails to initialize."""
    pass


# Pre-defined resource names for type safety
class ResourceNames:
    """Standard resource names used across the pipeline."""
    GIT_REPO = "git_repo"
    GITHUB_CLIENT = "github_client"
    LOG_STORAGE = "log_storage"
    WORKFLOW_RUN = "workflow_run"
    BUILD_SAMPLE_REPO = "build_sample_repo"

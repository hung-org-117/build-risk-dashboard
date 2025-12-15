"""
Resource DAG using Hamilton framework.

This module defines resources as Hamilton functions where dependencies
are expressed through function parameters. Hamilton automatically
resolves the DAG and determines execution order.

Usage:
    from app.tasks.pipeline.resource_dag import ResourceDAGRunner

    runner = ResourceDAGRunner()

    # Get ingestion tasks for required resources
    tasks = runner.get_ingestion_tasks(["git_worktree", "build_logs"])
    # Returns: ["clone_repo", "fetch_and_save_builds",
    #           "download_build_logs", "create_worktrees_batch"]

    # Get tasks grouped by level (for parallel execution)
    levels = runner.get_ingestion_tasks_by_level(["git_worktree", "build_logs"])
    # Returns: {0: ["clone_repo"], 1: ["create_worktrees_batch"]}
"""

import logging
from typing import Any, Dict, List, Optional, Set

from hamilton import driver
from hamilton.function_modifiers import tag

logger = logging.getLogger(__name__)


@tag(category="core")
def repo() -> List[str]:
    """Repository metadata - always available from DB."""
    return []  # No ingestion task


@tag(category="core")
def repo_config() -> List[str]:
    """User config - always available from DB."""
    return []


@tag(category="build")
def build_run() -> List[str]:
    """RawBuildRun entity - requires fetch_and_save_builds."""
    return ["fetch_and_save_builds"]


@tag(category="build")
def raw_build_runs() -> List[str]:
    return []


@tag(category="git")
def git_history() -> List[str]:
    return ["clone_repo"]


@tag(category="git")
def git_worktree(git_history: List[str]) -> List[str]:
    return git_history + ["create_worktrees_batch"]


@tag(category="build")
def build_logs(build_run: List[str]) -> List[str]:
    return build_run + ["download_build_logs"]


@tag(category="external")
def github_api() -> List[str]:
    return []


# =============================================================================
# Task dependency definitions for level calculation
# =============================================================================

# Define which tasks depend on which other tasks
TASK_DEPENDENCIES: Dict[str, List[str]] = {
    "clone_repo": [],
    "fetch_and_save_builds": [],
    "create_worktrees_batch": ["clone_repo"],
    "download_build_logs": ["fetch_and_save_builds"],
}


def _calculate_task_levels(tasks: List[str]) -> Dict[int, List[str]]:
    """
    Calculate execution levels for a list of tasks based on dependencies.

    Level 0: Tasks with no dependencies (or dependencies not in the list)
    Level 1: Tasks that depend only on level 0 tasks
    etc.

    Returns:
        Dict mapping level number to list of tasks at that level
    """
    if not tasks:
        return {}

    task_set = set(tasks)
    levels: Dict[int, List[str]] = {}
    assigned: Set[str] = set()
    max_iterations = len(tasks) + 1

    for iteration in range(max_iterations):
        current_level_tasks = []

        for task in tasks:
            if task in assigned:
                continue

            deps = TASK_DEPENDENCIES.get(task, [])
            # Check if all deps are either not in our task list OR already assigned
            deps_satisfied = all(dep not in task_set or dep in assigned for dep in deps)

            if deps_satisfied:
                current_level_tasks.append(task)

        if not current_level_tasks:
            break

        levels[iteration] = current_level_tasks
        assigned.update(current_level_tasks)

        if len(assigned) == len(task_set):
            break

    return levels


# =============================================================================
# Resource DAG Runner
# =============================================================================


class ResourceDAGRunner:
    """
    Runs the resource DAG to determine ingestion tasks.

    Uses Hamilton to automatically resolve resource dependencies
    and return the ordered list of ingestion tasks needed.
    """

    def __init__(self):
        self._driver = None
        self._all_resources: Optional[Set[str]] = None

    def _ensure_initialized(self):
        """Lazy initialize Hamilton driver."""
        if self._driver is None:
            import app.tasks.pipeline.resource_dag.dag as resource_module

            self._driver = driver.Builder().with_modules(resource_module).build()
            self._all_resources = self._get_all_resource_names()

    def _get_all_resource_names(self) -> Set[str]:
        """Get all available resource names."""
        return {v.name for v in self._driver.list_available_variables()}

    def get_all_resources(self) -> Set[str]:
        """Get set of all resource names."""
        self._ensure_initialized()
        return self._all_resources.copy()

    def get_ingestion_tasks(self, required_resources: List[str]) -> List[str]:
        """
        Get flat list of ingestion tasks for required resources.

        Returns tasks in dependency order (but not grouped by level).
        """
        if not required_resources:
            return []

        self._ensure_initialized()

        valid_resources = [r for r in required_resources if r in self._all_resources]

        if not valid_resources:
            logger.warning(f"No valid resources found in: {required_resources}")
            return []

        try:
            result = self._driver.execute(valid_resources, inputs={})
            all_tasks: List[str] = []
            seen: Set[str] = set()

            for resource_name in valid_resources:
                task_list = result.get(resource_name, [])
                if isinstance(task_list, list):
                    for task in task_list:
                        if task and task not in seen:
                            all_tasks.append(task)
                            seen.add(task)

            return all_tasks

        except Exception as e:
            logger.error(f"Failed to resolve resource DAG: {e}")
            return []

    def get_ingestion_tasks_by_level(
        self, required_resources: List[str]
    ) -> Dict[int, List[str]]:
        """
        Get ingestion tasks grouped by execution level.

        Level 0: Tasks with no dependencies (can run immediately)
        Level 1: Tasks that depend on level 0 tasks (run after level 0)
        etc.

        This allows building Celery workflows with proper chain/group structure:
        - Tasks at the same level can run in parallel (group)
        - Tasks at different levels run sequentially (chain)

        Example:
            {0: ["clone_repo"], 1: ["create_worktrees_batch", "download_build_logs"]}
            -> chain(clone_repo, group(create_worktrees, download_logs))
        """
        tasks = self.get_ingestion_tasks(required_resources)
        return _calculate_task_levels(tasks)

    def visualize(self) -> str:
        """Get DAG visualization (graphviz DOT format)."""
        try:
            return self._driver.display_all_functions()
        except Exception:
            return "DAG visualization not available"


# Singleton instance for convenience
_runner: Optional[ResourceDAGRunner] = None


def get_resource_dag_runner() -> ResourceDAGRunner:
    """Get singleton ResourceDAGRunner instance."""
    global _runner
    if _runner is None:
        _runner = ResourceDAGRunner()
    return _runner


def get_ingestion_tasks(required_resources: List[str]) -> List[str]:
    """Convenience function to get ingestion tasks."""
    return get_resource_dag_runner().get_ingestion_tasks(required_resources)


def get_ingestion_tasks_by_level(required_resources: List[str]) -> Dict[int, List[str]]:
    """Convenience function to get ingestion tasks grouped by level."""
    return get_resource_dag_runner().get_ingestion_tasks_by_level(required_resources)

"""
Resource DAG - Task resolution for ingestion pipelines.

This module provides functions to determine which ingestion tasks
are required for given resources.
"""

import logging
from typing import Dict, List, Set

from app.tasks.pipeline.shared.resources import (
    RESOURCE_LEAF_TASKS,
    TASK_DEPENDENCIES,
    FeatureResource,
)

logger = logging.getLogger(__name__)


# Task Resolution Functions
def _resolve_dependencies(tasks: List[str]) -> List[str]:
    """
    Resolve all task dependencies recursively.

    Returns tasks in dependency order (dependencies first).
    """
    resolved: List[str] = []
    seen: Set[str] = set()

    def add_with_deps(task: str):
        if task in seen:
            return
        seen.add(task)
        for dep in TASK_DEPENDENCIES.get(task, []):
            add_with_deps(dep)
        resolved.append(task)

    for task in tasks:
        add_with_deps(task)

    return resolved


def get_tasks_for_resources(resources: List[FeatureResource]) -> List[str]:
    """
    Get all ingestion tasks required for multiple resources.

    Args:
        resources: List of FeatureResource to get tasks for

    Returns:
        List of unique task names in dependency order
    """
    all_leaf_tasks: List[str] = []
    seen: Set[str] = set()

    for resource in resources:
        for task in RESOURCE_LEAF_TASKS.get(resource, []):
            if task not in seen:
                all_leaf_tasks.append(task)
                seen.add(task)

    return _resolve_dependencies(all_leaf_tasks)


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


def get_ingestion_tasks(required_resources: List[str]) -> List[str]:
    """
    Get flat list of ingestion tasks for required resources.

    Args:
        required_resources: List of resource names (strings)

    Returns:
        List of task names in dependency order
    """
    if not required_resources:
        return []

    # Convert string resource names to FeatureResource enum
    resources: List[FeatureResource] = []
    for r in required_resources:
        try:
            resources.append(FeatureResource(r))
        except ValueError:
            logger.warning(f"Unknown resource: {r}")

    if not resources:
        return []

    return get_tasks_for_resources(resources)


def get_ingestion_tasks_by_level(required_resources: List[str]) -> Dict[int, List[str]]:
    tasks = get_ingestion_tasks(required_resources)
    return _calculate_task_levels(tasks)

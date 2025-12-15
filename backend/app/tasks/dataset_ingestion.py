"""
Dataset Ingestion Tasks - Resource preparation for dataset builds.

This module uses shared ingestion infrastructure to prepare resources
(clone, worktree, logs) for dataset builds. It leverages resource_dag
to automatically determine which tasks are needed based on selected features.
"""

import logging
from typing import Any, Dict, List, Optional

from app.celery_app import celery_app
from app.repositories.dataset_repo_config import DatasetRepoConfigRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.tasks.base import PipelineTask
from app.tasks.pipeline.feature_dag._metadata import get_required_resources_for_features
from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
from app.tasks.shared import build_ingestion_workflow

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.dataset_ingestion.ingest_dataset_builds",
    queue="ingestion",
)
def ingest_dataset_builds(
    self: PipelineTask,
    repo_id: str,
    build_ids: List[str],
    features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Orchestrate resource preparation for dataset builds.

    Uses resource_dag to determine required ingestion tasks based on selected features.
    Tasks are grouped by level:
    - Level 0 tasks run first (e.g., clone_repo)
    - Level 1 tasks run after level 0, in parallel if multiple (e.g., worktrees, logs)
    """
    dataset_repo_config_repo = DatasetRepoConfigRepository(self.db)
    build_run_repo = RawBuildRunRepository(self.db)

    repo_config = dataset_repo_config_repo.find_by_id(repo_id)
    if not repo_config:
        raise ValueError(f"Dataset repo config {repo_id} not found")

    full_name = repo_config.normalized_full_name
    ci_provider = repo_config.ci_provider

    # Determine required resources using feature_dag metadata
    feature_set = set(features) if features else set()
    required_resources = get_required_resources_for_features(feature_set)

    # Get tasks grouped by level from resource_dag
    tasks_by_level = get_ingestion_tasks_by_level(list(required_resources))

    logger.info(
        f"Required resources: {required_resources}, tasks by level: {tasks_by_level}"
    )

    if not tasks_by_level:
        return {"status": "skipped", "reason": "No resources required"}

    # Get commit SHAs for worktree creation
    commit_shas = []
    for build_id in build_ids:
        # Use existing raw_repo_id from config to find the build run
        target_repo_id = str(repo_config.raw_repo_id)
        build = build_run_repo.find_by_repo_and_build_id(target_repo_id, build_id)
        if build and build.commit_sha:
            commit_shas.append(build.effective_sha or build.commit_sha)
    commit_shas = list(set(commit_shas))
    build_ids = list(set(build_ids))

    # Build workflow using shared helper
    workflow = build_ingestion_workflow(
        tasks_by_level=tasks_by_level,
        raw_repo_id=repo_config.raw_repo_id,
        full_name=full_name,
        build_ids=build_ids,
        commit_shas=commit_shas,
        ci_provider=ci_provider,
    )

    if not workflow:
        return {"status": "skipped", "reason": "No applicable tasks"}

    workflow.apply_async()

    return {
        "status": "dispatched",
        "repo_id": repo_id,
        "builds": len(build_ids),
        "resources": list(required_resources),
        "tasks_by_level": {str(k): v for k, v in tasks_by_level.items()},
    }

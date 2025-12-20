"""
Dataset Ingestion Tasks - Resource preparation for dataset builds.

This module uses shared ingestion infrastructure to prepare resources
(clone, worktree, logs) for dataset builds. It leverages resource_dag
to automatically determine which tasks are needed based on selected features.

Flow (similar to model_ingestion):
1. Determine required resources based on selected features
2. Build ingestion workflow (clone → worktrees → logs)
3. If final_task provided: append to workflow chain (async)
4. If no final_task: wait for workflow completion (sync)
"""

import logging
from typing import Any, Dict, List, Optional

from celery.canvas import Signature

from app.celery_app import celery_app
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dataset_version import DatasetVersionRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import PipelineTask
from app.tasks.pipeline.feature_dag._metadata import get_required_resources_for_features
from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
from app.tasks.shared import build_ingestion_workflow

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.dataset_ingestion.ingest_dataset_builds_for_repo",
    queue="ingestion",
    soft_time_limit=1800,  # 30 min
    time_limit=1860,
)
def ingest_dataset_builds_for_repo(
    self: PipelineTask,
    version_id: str,
    raw_repo_id: str,
    build_csv_ids: List[str],
    features: Optional[List[str]] = None,
    final_task: Optional[Signature] = None,
) -> Dict[str, Any]:
    """
    Orchestrate resource preparation for dataset builds.

    Uses resource_dag to determine required ingestion tasks based on selected features.
    Tasks are grouped by level:
    - Level 0 tasks run first (e.g., clone_repo)
    - Level 1 tasks run after level 0 (e.g., worktrees, logs)

    Args:
        version_id: DatasetVersion ID
        raw_repo_id: RawRepository ID
        build_csv_ids: List of build IDs from CSV
        features: Optional list of features to extract
        final_task: Optional task to append after ingestion (like dispatch_enrichment)

    If final_task is provided, it runs AFTER ingestion (chained).
    If no final_task, waits for ingestion to complete synchronously.
    """
    version_repo = DatasetVersionRepository(self.db)
    dataset_repo = DatasetRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)
    build_run_repo = RawBuildRunRepository(self.db)

    # Get version and dataset for ci_provider lookup
    dataset_version = version_repo.find_by_id(version_id)
    if not dataset_version:
        raise ValueError(f"Dataset version {version_id} not found")

    dataset = dataset_repo.find_by_id(dataset_version.dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_version.dataset_id} not found")

    # Get raw repository
    raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
    if not raw_repo:
        raise ValueError(f"RawRepository {raw_repo_id} not found")

    full_name = raw_repo.full_name

    # Get CI provider from dataset.repo_ci_providers (set during validation)
    ci_provider = "github_actions"  # default
    if dataset.repo_ci_providers:
        ci_provider = dataset.repo_ci_providers.get(raw_repo_id, "github_actions")

    # Determine required resources using feature_dag metadata
    feature_set = set(features) if features else set()
    required_resources = get_required_resources_for_features(feature_set)

    # Get tasks grouped by level from resource_dag
    tasks_by_level = get_ingestion_tasks_by_level(list(required_resources))

    logger.info(
        f"[Dataset Ingestion] {full_name}: resources={required_resources}, "
        f"tasks_by_level={tasks_by_level}"
    )

    if not tasks_by_level:
        # No ingestion needed, run final_task directly if provided
        if final_task:
            final_task.apply_async()
            return {
                "status": "dispatched",
                "reason": "No resources required, final_task dispatched",
            }
        return {"status": "skipped", "reason": "No resources required"}

    # Get commit SHAs for worktree creation
    commit_shas = []
    for build_csv_id in build_csv_ids:
        raw_build_run = build_run_repo.find_by_business_key(raw_repo_id, build_csv_id, ci_provider)
        if raw_build_run and raw_build_run.commit_sha:
            commit_shas.append(raw_build_run.effective_sha or raw_build_run.commit_sha)
    commit_shas = list(set(commit_shas))
    build_csv_ids = list(set(build_csv_ids))

    # Build workflow using shared helper (with optional final_task)
    workflow = build_ingestion_workflow(
        tasks_by_level=tasks_by_level,
        raw_repo_id=raw_repo_id,
        full_name=full_name,
        build_ids=build_csv_ids,
        commit_shas=commit_shas,
        ci_provider=ci_provider,
        final_task=final_task,  # Chain processing AFTER ingestion
    )

    if not workflow:
        if final_task:
            final_task.apply_async()
            return {
                "status": "dispatched",
                "reason": "No applicable tasks, final_task dispatched",
            }
        return {"status": "skipped", "reason": "No applicable tasks"}

    if final_task:
        # Async: workflow includes final_task in chain
        workflow.apply_async()
        return {
            "status": "dispatched",
            "version_id": version_id,
            "raw_repo_id": raw_repo_id,
            "build_csv_ids": len(build_csv_ids),
            "resources": list(required_resources),
            "has_final_task": True,
        }
    else:
        # Sync: wait for ingestion to complete
        workflow.apply_async().get(timeout=1800, disable_sync_subtasks=False)
        return {
            "status": "completed",
            "version_id": version_id,
            "raw_repo_id": raw_repo_id,
            "build_csv_ids": len(build_csv_ids),
            "resources": list(required_resources),
        }

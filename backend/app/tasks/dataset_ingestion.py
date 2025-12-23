"""
Dataset Ingestion Tasks - Resource preparation for dataset builds.

This module uses shared ingestion infrastructure to prepare resources
(clone, worktree, logs) for dataset builds. It leverages resource_dag
to automatically determine which tasks are needed based on selected features.

Flow (Celery chord pattern):
1. Determine required resources based on selected features
2. Build ingestion chain per repo (clone → worktrees → logs)
3. Chains are grouped and run in parallel via chord in enrichment_processing
4. Chord callback aggregates results after ALL chains complete
"""

import logging
import uuid
from typing import Dict, List, Optional

from celery.canvas import Signature

from app.tasks.shared import build_ingestion_workflow

logger = logging.getLogger(__name__)


def build_repo_ingestion_chain(
    raw_repo_id: str,
    github_repo_id: int,
    full_name: str,
    build_csv_ids: List[str],
    commit_shas: List[str],
    ci_provider: str,
    tasks_by_level: Dict[int, List[str]],
    correlation_id: str = "",
) -> Optional[Signature]:
    """
    Build a Celery chain for ingesting a single repository.

    Returns a chain: clone_repo → create_worktrees → download_build_logs
    (only includes tasks that are required based on features).

    This chain can be added to a group() for parallel execution across repos.

    Args:
        raw_repo_id: Repository MongoDB ID
        github_repo_id: GitHub's internal repository ID for paths
        full_name: Repository full name (owner/repo)
        build_csv_ids: List of build IDs for log download
        commit_shas: List of commit SHAs for worktree creation
        ci_provider: CI provider string
        tasks_by_level: Dict of level -> task names from resource_dag
        correlation_id: Optional correlation ID for tracing

    Returns:
        Celery chain signature, or None if no tasks needed
    """
    # Generate correlation_id if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    corr_prefix = f"[corr={correlation_id[:8]}]"
    logger.info(
        f"{corr_prefix}[dataset_ingestion] Building chain for {full_name} "
        f"with {len(build_csv_ids)} builds, {len(commit_shas)} commits"
    )

    return build_ingestion_workflow(
        tasks_by_level=tasks_by_level,
        raw_repo_id=raw_repo_id,
        github_repo_id=github_repo_id,
        full_name=full_name,
        build_ids=build_csv_ids,
        commit_shas=commit_shas,
        ci_provider=ci_provider,
        correlation_id=correlation_id,
    )

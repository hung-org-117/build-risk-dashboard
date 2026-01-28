"""
Training Processing - Scan Tasks.

Contains:
- dispatch_scenario_scans: Dispatch scans for all commits
- process_scan_batch: Process single batch of scan dispatches
- finalize_scan_dispatch: Finalize after scan dispatch complete
"""

import logging
from typing import Any, Dict, List

from bson import ObjectId

from app.celery_app import celery_app
from app.entities.training_ingestion_build import IngestionStatus
from app.paths import get_worktree_path
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.dispatch_scenario_scans",
    queue="scenario_scanning",
    soft_time_limit=300,
    time_limit=600,
)
def dispatch_scenario_scans(
    self: SafeTask,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Dispatch scans for all unique commits in scenario's ingested builds.

    Fire-and-forget: runs parallel to feature extraction.
    """
    from celery import chain

    def mark_failed(e: Exception):
        # For scan dispatch, we don't fail the scenario - just log the error
        logger.error(f"Scan dispatch failed for {scenario_id}: {e}")

    def _work(state: TaskState) -> Dict[str, Any]:
        from app.config import settings

        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

        scenario_repo = TrainingScenarioRepository(self.db)
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
        raw_build_run_repo = RawBuildRunRepository(self.db)
        raw_repo_repo = RawRepositoryRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Get scan_metrics config
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            scan_metrics_config = feature_config.get("scan_metrics", {})
        else:
            scan_metrics_config = getattr(feature_config, "scan_metrics", {}) or {}

        has_sonar = bool(scan_metrics_config.get("sonarqube"))
        has_trivy = bool(scan_metrics_config.get("trivy"))

        if not has_sonar and not has_trivy:
            logger.info(f"{corr_prefix} No scan metrics configured, skipping")
            return {"status": "skipped", "reason": "No scan metrics configured"}

        # Collect unique commits
        commits_to_scan: Dict[tuple, Dict[str, Any]] = {}
        repo_cache: Dict[str, Any] = {}

        ingested_builds, _ = ingestion_build_repo.find_by_scenario(
            scenario_id=scenario_id,
            status_filter=IngestionStatus.INGESTED,
        )

        raw_build_run_ids = [
            b.raw_build_run_id for b in ingested_builds if b.raw_build_run_id
        ]
        raw_build_runs = raw_build_run_repo.find_by_ids(
            [str(rid) for rid in raw_build_run_ids]
        )
        build_run_map = {str(r.id): r for r in raw_build_runs}

        for build in ingested_builds:
            raw_run = build_run_map.get(str(build.raw_build_run_id))
            if not raw_run or not raw_run.commit_sha:
                continue

            commit_key = (str(build.raw_repo_id), raw_run.commit_sha)
            if commit_key in commits_to_scan:
                continue

            if str(build.raw_repo_id) not in repo_cache:
                raw_repo = raw_repo_repo.find_by_id(str(build.raw_repo_id))
                if raw_repo:
                    repo_cache[str(build.raw_repo_id)] = raw_repo

            raw_repo = repo_cache.get(str(build.raw_repo_id))
            if not raw_repo:
                continue

            commits_to_scan[commit_key] = {
                "raw_repo_id": str(build.raw_repo_id),
                "github_repo_id": raw_repo.github_repo_id,
                "commit_sha": raw_run.commit_sha,
                "repo_full_name": raw_repo.full_name,
            }

            # Check if worktree exists (otherwise dispatch will skip it)
            worktree_path = get_worktree_path(
                raw_repo.github_repo_id, raw_run.commit_sha
            )
            if not worktree_path.exists():
                logger.warning(
                    f"{corr_prefix} Skipping scan for {raw_run.commit_sha[:8]} - "
                    f"worktree not found at {worktree_path}"
                )
                del commits_to_scan[commit_key]

        if not commits_to_scan:
            logger.info(f"{corr_prefix} No commits to scan")
            updated_scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "scans_total": 0,
                        "scan_extraction_completed": True,
                    }
                },
                return_updated=True,
            )
            if updated_scenario:
                publish_scenario_updated(updated_scenario)
            return {"status": "skipped", "reason": "No commits found"}

        # Calculate scans_total
        enabled_tools = (1 if has_sonar else 0) + (1 if has_trivy else 0)
        scans_total = len(commits_to_scan) * enabled_tools

        scenario_repo.set_scans_total(scenario_id, scans_total)

        # Split into batches
        commits_list = list(commits_to_scan.values())
        batch_size = getattr(settings, "SCAN_COMMITS_PER_BATCH", 20)
        batches = [
            commits_list[i : i + batch_size]
            for i in range(0, len(commits_list), batch_size)
        ]

        logger.info(
            f"{corr_prefix} Dispatching {len(commits_list)} commits in {len(batches)} batches"
        )

        # Chain batches
        batch_tasks = [
            process_scan_batch.si(
                scenario_id=scenario_id,
                commits_batch=batch,
                batch_index=i,
                total_batches=len(batches),
                scan_metrics_config=scan_metrics_config,
                correlation_id=correlation_id,
            )
            for i, batch in enumerate(batches)
        ]

        if batch_tasks:
            workflow = chain(
                *batch_tasks,
                finalize_scan_dispatch.si(
                    scenario_id=scenario_id,
                    total_commits=len(commits_list),
                    total_batches=len(batches),
                    has_sonar=has_sonar,
                    has_trivy=has_trivy,
                    correlation_id=correlation_id,
                ),
            )
            workflow.apply_async()

        # Refresh scenario with updated scans_total and publish
        scenario = scenario_repo.find_by_id(scenario_id)
        if scenario:
            publish_scenario_updated(scenario)

        return {
            "status": "dispatched",
            "total_commits": len(commits_list),
            "scans_total": scans_total,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_processing.process_scan_batch",
    queue="scenario_scanning",
    soft_time_limit=120,
    time_limit=180,
)
def process_scan_batch(
    self: PipelineTask,
    scenario_id: str,
    commits_batch: List[Dict[str, Any]],
    batch_index: int,
    total_batches: int,
    scan_metrics_config: Dict[str, List[str]],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Process a single batch of scan dispatches.

    Rate limiting: Adds configurable delay between scan dispatches to prevent
    overwhelming SonarQube/Trivy servers. Default: 0.5s between scans.
    """
    import time

    from app.config import settings

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(f"{corr_prefix} [scan_batch] Batch {batch_index + 1}/{total_batches}")

    from app.tasks.training_scan_helpers import dispatch_scan_for_scenario_commit

    # Delay between scan dispatches (seconds)
    scan_dispatch_delay = getattr(settings, "SCAN_DISPATCH_DELAY_SECONDS", 0.5)

    dispatched = 0
    for i, commit_info in enumerate(commits_batch):
        try:
            dispatch_scan_for_scenario_commit.delay(
                scenario_id=scenario_id,
                raw_repo_id=commit_info["raw_repo_id"],
                github_repo_id=commit_info["github_repo_id"],
                commit_sha=commit_info["commit_sha"],
                repo_full_name=commit_info["repo_full_name"],
                scan_metrics_config=scan_metrics_config,
            )
            dispatched += 1

            # Rate limiting: delay between dispatches (except last one)
            if scan_dispatch_delay > 0 and i < len(commits_batch) - 1:
                time.sleep(scan_dispatch_delay)

        except Exception as e:
            logger.warning(f"{corr_prefix} Failed to dispatch: {e}")

    return {"status": "completed", "batch_index": batch_index, "dispatched": dispatched}


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_processing.finalize_scan_dispatch",
    queue="scenario_scanning",
    soft_time_limit=60,
    time_limit=120,
)
def finalize_scan_dispatch(
    self: PipelineTask,
    scenario_id: str,
    total_commits: int,
    total_batches: int,
    has_sonar: bool,
    has_trivy: bool,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Finalize scan dispatch after all batches complete.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(
        f"{corr_prefix} Scan dispatch completed: {total_commits} commits, "
        f"sonar={has_sonar}, trivy={has_trivy}"
    )

    return {
        "status": "completed",
        "total_commits": total_commits,
        "total_batches": total_batches,
    }

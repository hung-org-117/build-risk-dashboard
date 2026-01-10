"""
ML Scenario Scan Dispatch Helpers.

Entry point: dispatch_scan_for_scenario_commit
- Dispatches Trivy scan to trivy_scan queue
- Dispatches SonarQube scan to sonar_scan queue

Reuses existing scan tasks from trivy.py and sonar.py.
Uses scenario_id as the context identifier (like version_id in enrichment).
"""

import logging
from typing import Any, Dict, List

from app.celery_app import celery_app
from app.core.tracing import TracingContext
from app.paths import get_worktree_path
from app.tasks.base import PipelineTask

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_scan_helpers.dispatch_scan_for_scenario_commit",
    queue="scenario_scanning",
    soft_time_limit=60,
    time_limit=120,
)
def dispatch_scan_for_scenario_commit(
    self: PipelineTask,
    scenario_id: str,
    raw_repo_id: str,
    github_repo_id: int,
    commit_sha: str,
    repo_full_name: str,
    scan_metrics_config: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Dispatch scans for a single commit in an ML scenario.

    Reuses existing scan tasks (start_trivy_scan_for_version_commit,
    start_sonar_scan_for_version_commit) by passing scenario_id
    as the context identifier.

    Args:
        scenario_id: MLScenario ID (used as context ID for scans)
        raw_repo_id: RawRepository MongoDB ID
        github_repo_id: GitHub's internal repository ID for paths
        commit_sha: Commit SHA to scan
        repo_full_name: Repository full name (owner/repo)
        scan_metrics_config: Dict with {"sonarqube": [...], "trivy": [...]}
    """
    correlation_id = TracingContext.get_correlation_id() or ""
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # Check if worktree exists before dispatching any scans
    worktree_path = get_worktree_path(github_repo_id, commit_sha)
    if not worktree_path.exists():
        logger.warning(
            f"{corr_prefix} Skipping scans for {commit_sha[:8]} - "
            f"worktree not found at {worktree_path}"
        )
        return {
            "status": "skipped",
            "reason": "worktree_not_found",
            "commit_sha": commit_sha,
        }

    results = {"trivy": None, "sonarqube": None}

    # Dispatch Trivy scan
    trivy_metrics = scan_metrics_config.get("trivy", [])
    if trivy_metrics:
        try:
            from app.tasks.trivy import start_trivy_scan_for_version_commit

            # Reuse version scan task - scenario_id acts as version_id
            start_trivy_scan_for_version_commit.delay(
                version_id=scenario_id,  # Use scenario_id as context
                commit_sha=commit_sha,
                repo_full_name=repo_full_name,
                raw_repo_id=raw_repo_id,
                github_repo_id=github_repo_id,
                trivy_config={},  # Default config for ML scenarios
                selected_metrics=trivy_metrics,
                config_file_path="",
                correlation_id=correlation_id,
            )

            results["trivy"] = {"status": "dispatched"}
            logger.info(
                f"{corr_prefix} Dispatched Trivy scan for commit {commit_sha[:8]}"
            )

        except Exception as exc:
            logger.warning(
                f"{corr_prefix} Failed to dispatch Trivy scan for {commit_sha[:8]}: {exc}"
            )
            results["trivy"] = {"status": "error", "error": str(exc)}

    # Dispatch SonarQube scan
    sonar_metrics = scan_metrics_config.get("sonarqube", [])
    if sonar_metrics:
        try:
            from app.tasks.sonar import start_sonar_scan_for_version_commit

            # Generate component key with scenario_id prefix for uniqueness
            repo_name_safe = repo_full_name.replace("/", "_")
            scenario_prefix = scenario_id[:8]
            component_key = (
                f"scenario_{scenario_prefix}_{repo_name_safe}_{commit_sha[:12]}"
            )

            # Reuse version scan task - scenario_id acts as version_id
            start_sonar_scan_for_version_commit.delay(
                version_id=scenario_id,  # Use scenario_id as context
                commit_sha=commit_sha,
                repo_full_name=repo_full_name,
                raw_repo_id=raw_repo_id,
                github_repo_id=github_repo_id,
                component_key=component_key,
                config_file_path="",
                correlation_id=correlation_id,
            )

            results["sonarqube"] = {
                "status": "dispatched",
                "component_key": component_key,
            }
            logger.info(
                f"{corr_prefix} Dispatched SonarQube scan for commit {commit_sha[:8]}"
            )

        except Exception as exc:
            logger.warning(
                f"{corr_prefix} Failed to dispatch SonarQube for {commit_sha[:8]}: {exc}"
            )
            results["sonarqube"] = {"status": "error", "error": str(exc)}

    return {
        "status": "dispatched",
        "commit_sha": commit_sha,
        "correlation_id": correlation_id,
        "results": results,
    }

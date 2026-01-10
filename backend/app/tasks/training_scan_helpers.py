"""
Training Scenario Scan Dispatch Helpers.

Entry point: dispatch_scan_for_scenario_commit
- Dispatches Trivy scan to trivy_scan queue
- Dispatches SonarQube scan to sonar_scan queue

Adapted from enrichment_scan_helpers.py for TrainingScenario.
"""

import logging
from typing import Any, Dict, Optional

from app.celery_app import celery_app
from app.core.tracing import TracingContext
from app.paths import get_sonarqube_config_path, get_trivy_config_path
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask

logger = logging.getLogger(__name__)


def _write_config_file(config_path, content: str) -> bool:
    """Write config content to file, creating directories if needed."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(content)
        logger.info(f"Wrote config to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write config to {config_path}: {e}")
        return False


def _get_repo_config(tool_config: dict, github_repo_id: int) -> dict:
    """
    Get scan config for a specific repo.

    Returns repo-specific config from 'repos' dict.
    No global fallback - each repo must have explicit config or empty dict returned.
    """
    return tool_config.get("repos", {}).get(str(github_repo_id), {})


def _build_sonar_config_content(sonar_config: dict) -> Optional[str]:
    """Build sonar-project.properties content from config dict (extraProperties only)."""
    if sonar_config.get("extraProperties"):
        return sonar_config["extraProperties"].strip()
    return None


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_scan_helpers.dispatch_scan_for_scenario_commit",
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
    scan_metrics_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Dispatch scans for a single commit within a training scenario.

    Creates tracking records and dispatches tasks to dedicated queues.

    Args:
        scenario_id: TrainingScenario ID
        raw_repo_id: RawRepository MongoDB ID
        github_repo_id: GitHub's internal repository ID for paths
        commit_sha: Commit SHA to scan
        repo_full_name: Repository full name (owner/repo)
        scan_metrics_config: Optional override for what metrics to collect
    """
    # Get correlation_id from tracing context (set by parent task)
    correlation_id = TracingContext.get_correlation_id()
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # Check if worktree exists before dispatching any scans
    from app.paths import get_worktree_path

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

    scenario_repo = TrainingScenarioRepository(self.db)
    scenario = scenario_repo.find_by_id(scenario_id)

    if not scenario:
        logger.error(f"{corr_prefix} Scenario {scenario_id} not found")
        return {"status": "error", "error": "Scenario not found"}

    # Use passed config or fall back to scenario config
    if not scan_metrics_config:
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            scan_metrics_config = feature_config.get("scan_metrics", {})
        else:
            scan_metrics_config = getattr(feature_config, "scan_metrics", {}) or {}

    # Get tool configs (for custom yaml/properties)
    # Stored in feature_config extra fields or scan_config field if it exists
    feature_config_obj = scenario.feature_config
    if isinstance(feature_config_obj, dict):
        scan_tool_config = feature_config_obj.get("scan_config", {})
    else:
        scan_tool_config = getattr(feature_config_obj, "scan_config", {}) or {}

    results = {"trivy": None, "sonarqube": None}

    # Dispatch Trivy scan
    trivy_metrics = scan_metrics_config.get("trivy", [])
    if trivy_metrics:
        try:
            # Get repo-specific or default trivy config
            trivy_tool_config = scan_tool_config.get("trivy", {})
            trivy_config = _get_repo_config(trivy_tool_config, github_repo_id)

            # Get config content (trivyYaml)
            trivy_yaml = trivy_config.get("trivyYaml", "")

            # Write config to external path (only if not exists)
            trivy_config_path = None
            if trivy_yaml:
                # Use scenario_id as version_id/context identifier
                trivy_config_path = get_trivy_config_path(scenario_id, github_repo_id)
                if not trivy_config_path.exists():
                    _write_config_file(trivy_config_path, trivy_yaml)

            from app.tasks.trivy import start_trivy_scan_for_version_commit

            # Note: We reuse start_trivy_scan_for_version_commit but pass scenario_id as version_id
            start_trivy_scan_for_version_commit.delay(
                version_id=scenario_id,
                commit_sha=commit_sha,
                repo_full_name=repo_full_name,
                raw_repo_id=raw_repo_id,
                github_repo_id=github_repo_id,
                trivy_config=trivy_config,
                config_file_path=str(trivy_config_path) if trivy_config_path else None,
                selected_metrics=trivy_metrics,
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
            # Get repo-specific or default sonar config
            sonar_tool_config = scan_tool_config.get("sonarqube", {})
            sonar_config = _get_repo_config(sonar_tool_config, github_repo_id)

            # Generate component key with scenario_id prefix for uniqueness
            repo_name_safe = repo_full_name.replace("/", "_")
            scenario_prefix = scenario_id[:8]
            component_key = f"{scenario_prefix}_{repo_name_safe}_{commit_sha[:12]}"

            config_content = _build_sonar_config_content(sonar_config)

            # Write config to external path (only if not exists)
            sonar_config_path = None
            if config_content:
                # Use scenario_id as version_id/context identifier
                sonar_config_path = get_sonarqube_config_path(
                    scenario_id, github_repo_id
                )
                if not sonar_config_path.exists():
                    _write_config_file(sonar_config_path, config_content)

            from app.tasks.sonar import start_sonar_scan_for_version_commit

            # Note: We reuse start_sonar_scan_for_version_commit but pass scenario_id as version_id
            start_sonar_scan_for_version_commit.delay(
                version_id=scenario_id,
                commit_sha=commit_sha,
                repo_full_name=repo_full_name,
                raw_repo_id=raw_repo_id,
                github_repo_id=github_repo_id,
                component_key=component_key,
                config_file_path=str(sonar_config_path) if sonar_config_path else None,
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
                f"{corr_prefix} Failed to dispatch SonarQube scan for {commit_sha[:8]}: {exc}"
            )
            results["sonarqube"] = {"status": "error", "error": str(exc)}

    return {
        "status": "dispatched",
        "commit_sha": commit_sha,
        "correlation_id": correlation_id,
        "results": results,
    }

"""
Training Processing - Retry Tasks.

Contains:
- reprocess_failed_feature_extraction: Retry FAILED enrichment builds
- retry_failed_scenario_scans: Retry failed scans (tool-specific)
- process_retry_scan_batch: Process single batch of scan retries
"""

import logging
from typing import Any, Dict, List

from bson import ObjectId
from celery import chain

from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.training.processing.base import ScenarioProcessingTask
from app.tasks.training.processing.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=ScenarioProcessingTask,
    name="app.tasks.training_processing.reprocess_failed_feature_extraction",
    queue="scenario_processing",
    soft_time_limit=300,
    time_limit=360,
)
def reprocess_failed_feature_extraction(
    self: ScenarioProcessingTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Reprocess only FAILED enrichment builds for a scenario.

    Uses sequential chain to ensure temporal features work correctly.
    """
    # Import here to avoid circular imports
    from app.tasks.training.processing.enrichment import process_single_enrichment
    from app.tasks.training.processing.finalize import finalize_feature_extraction

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        import uuid

        correlation_id = str(uuid.uuid4())

        scenario_repo = TrainingScenarioRepository(self.db)
        enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "message": "Scenario not found"}

        # Find FAILED enrichment builds
        failed_builds, _ = enrichment_build_repo.find_by_scenario(
            scenario_id, extraction_status=ExtractionStatus.FAILED
        )

        if not failed_builds:
            return {
                "status": "no_failed_builds",
                "message": "No failed builds to retry",
            }

        # Reset FAILED builds to PENDING
        reset_count = 0
        for build in failed_builds:
            enrichment_build_repo.update_one(
                str(build.id),
                {
                    "extraction_status": ExtractionStatus.PENDING.value,
                    "extraction_error": None,
                    "feature_vector_id": None,
                },
            )
            reset_count += 1

        # Get selected features from scenario
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            dag_features = feature_config.get("dag_features", [])
        else:
            dag_features = getattr(feature_config, "dag_features", []) or []
        selected_features = dag_features if dag_features else []

        # Build reprocessing chain
        processing_tasks = [
            process_single_enrichment.si(
                scenario_id=scenario_id,
                enrichment_build_id=str(build.id),
                selected_features=selected_features,
                correlation_id=correlation_id,
            )
            for build in failed_builds
        ]

        workflow = chain(
            *processing_tasks,
            finalize_feature_extraction.si(
                scenario_id=scenario_id,
                created_count=0,
                correlation_id=correlation_id,
            ),
        )
        workflow.apply_async()

        logger.info(f"Dispatched reprocessing for {reset_count} failed builds")

        return {
            "status": "queued",
            "builds_reset": reset_count,
            "correlation_id": correlation_id,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.retry_failed_scenario_scans",
    queue="scenario_scanning",
    soft_time_limit=300,
    time_limit=600,
)
def retry_failed_scenario_scans(
    self: SafeTask,
    scenario_id: str,
    tool_type: str,
) -> Dict[str, Any]:
    """
    Retry failed scans for a specific tool type using batch processing.

    Collects failed scans, splits into batches, and dispatches via chain.
    Each batch checks if scan is already COMPLETED before dispatching.

    Args:
        scenario_id: TrainingScenario ID
        tool_type: Required - "trivy" or "sonarqube"
    """
    import uuid

    from app.config import settings

    correlation_id = str(uuid.uuid4())
    corr_prefix = f"[corr={correlation_id[:8]}]"

    if tool_type not in ("trivy", "sonarqube"):
        return {"status": "error", "error": f"Invalid tool_type: {tool_type}"}

    logger.info(
        f"{corr_prefix} Starting retry_failed_scenario_scans for {scenario_id}, "
        f"tool={tool_type}"
    )

    scenario_repo = TrainingScenarioRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    # Get scan_metrics config
    feature_config = scenario.feature_config
    if isinstance(feature_config, dict):
        scan_metrics_config = feature_config.get("scan_metrics", {})
        scan_tool_config = feature_config.get("scan_config", {})
    else:
        scan_metrics_config = getattr(feature_config, "scan_metrics", {}) or {}
        scan_tool_config = getattr(feature_config, "scan_config", {}) or {}

    # Collect failed scans info
    from app.tasks.training_scan_helpers import get_failed_scans_for_tool

    if tool_type == "trivy":
        trivy_metrics = scan_metrics_config.get("trivy", [])
        if not trivy_metrics:
            return {"status": "skipped", "message": "Trivy not configured"}

    elif tool_type == "sonarqube":
        sonar_metrics = scan_metrics_config.get("sonarqube", [])
        if not sonar_metrics:
            return {"status": "skipped", "message": "SonarQube not configured"}

    scans_to_retry = get_failed_scans_for_tool(self.db, tool_type, scenario_id)

    if not scans_to_retry:
        logger.info(f"{corr_prefix} No failed {tool_type} scans to retry")
        return {"status": "no_failed_scans", "message": "No failed scans to retry"}

    # Split into batches
    batch_size = getattr(settings, "SCAN_COMMITS_PER_BATCH", 20)
    batches = [
        scans_to_retry[i : i + batch_size] for i in range(0, len(scans_to_retry), batch_size)
    ]

    logger.info(
        f"{corr_prefix} Retrying {len(scans_to_retry)} {tool_type} scans "
        f"in {len(batches)} batches"
    )

    # Chain batches
    batch_tasks = [
        process_retry_scan_batch.s(
            scenario_id=scenario_id,
            tool_type=tool_type,
            scans_batch=batch,
            batch_index=i,
            total_batches=len(batches),
            scan_metrics_config=scan_metrics_config,
            scan_tool_config=scan_tool_config,
            correlation_id=correlation_id,
        )
        for i, batch in enumerate(batches)
    ]

    if batch_tasks:
        workflow = chain(*batch_tasks)
        workflow.apply_async()

    return {
        "status": "queued",
        "tool_type": tool_type,
        "scans_to_retry": len(scans_to_retry),
        "batches": len(batches),
        "correlation_id": correlation_id,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_processing.process_retry_scan_batch",
    queue="scenario_scanning",
    soft_time_limit=180,
    time_limit=300,
)
def process_retry_scan_batch(
    self: PipelineTask,
    scenario_id: str,
    tool_type: str,
    scans_batch: List[Dict[str, Any]],
    batch_index: int,
    total_batches: int,
    scan_metrics_config: Dict[str, List[str]],
    scan_tool_config: Dict[str, Any],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Process a single batch of scan retries.

    For each scan:
    1. Check if scan already COMPLETED (skip if so)
    2. Reset scan status to PENDING
    3. Dispatch to tool-specific scan task
    """
    from app.entities.sonar_commit_scan import SonarScanStatus
    from app.entities.trivy_commit_scan import TrivyScanStatus
    from app.repositories.raw_repository import RawRepositoryRepository
    from app.repositories.sonar_commit_scan import SonarCommitScanRepository
    from app.repositories.trivy_commit_scan import TrivyCommitScanRepository
    from app.tasks.sonar import start_sonar_scan_for_version_commit
    from app.tasks.training_scan_helpers import _get_repo_config
    from app.tasks.trivy import start_trivy_scan_for_version_commit

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(
        f"{corr_prefix} [retry_batch] Batch {batch_index + 1}/{total_batches} "
        f"for {tool_type} ({len(scans_batch)} scans)"
    )

    raw_repo_repo = RawRepositoryRepository(self.db)
    raw_repo_cache: Dict[str, Any] = {}

    dispatched = 0
    skipped_completed = 0
    skipped_missing = 0
    skipped_exists_on_server = 0

    if tool_type == "trivy":
        trivy_repo = TrivyCommitScanRepository(self.db)
        trivy_metrics = scan_metrics_config.get("trivy", [])
        trivy_tool_config = scan_tool_config.get("trivy", {})

        for scan_info in scans_batch:
            scan_id = ObjectId(scan_info["scan_id"])

            # Check current status - skip if already COMPLETED
            current_scan = trivy_repo.find_by_id(str(scan_id))
            if current_scan and current_scan.status == TrivyScanStatus.COMPLETED.value:
                logger.debug(
                    f"{corr_prefix} Skipping {scan_info['commit_sha'][:8]} - already completed"
                )
                skipped_completed += 1
                continue

            # Get raw repo
            raw_repo_id = scan_info["raw_repo_id"]
            if raw_repo_id not in raw_repo_cache:
                raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
                if raw_repo:
                    raw_repo_cache[raw_repo_id] = raw_repo

            raw_repo = raw_repo_cache.get(raw_repo_id)
            if not raw_repo:
                skipped_missing += 1
                continue

            # Reset scan status
            trivy_repo.increment_retry(scan_id)

            # Get repo-specific config
            trivy_config = _get_repo_config(trivy_tool_config, raw_repo.github_repo_id)

            # Dispatch to Trivy scan task
            start_trivy_scan_for_version_commit.delay(
                scenario_id=scenario_id,
                commit_sha=scan_info["commit_sha"],
                repo_full_name=scan_info["repo_full_name"],
                raw_repo_id=raw_repo_id,
                github_repo_id=raw_repo.github_repo_id,
                trivy_config=trivy_config,
                config_file_path=None,
                selected_metrics=trivy_metrics,
                correlation_id=correlation_id,
            )
            dispatched += 1

    elif tool_type == "sonarqube":
        sonar_repo = SonarCommitScanRepository(self.db)

        # Initialize SonarQube tool for existence checks
        from app.integrations.tools.sonarqube.tool import SonarQubeTool

        sonar_tool = SonarQubeTool()

        for scan_info in scans_batch:
            scan_id = ObjectId(scan_info["scan_id"])

            # Check current status - skip if already COMPLETED in DB
            current_scan = sonar_repo.find_by_id(str(scan_id))
            if current_scan and current_scan.status == SonarScanStatus.COMPLETED.value:
                logger.debug(f"{corr_prefix} Skip {scan_info['commit_sha'][:8]} - completed in DB")
                skipped_completed += 1
                continue

            # Get raw repo
            raw_repo_id = scan_info["raw_repo_id"]
            if raw_repo_id not in raw_repo_cache:
                raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
                if raw_repo:
                    raw_repo_cache[raw_repo_id] = raw_repo

            raw_repo = raw_repo_cache.get(raw_repo_id)
            if not raw_repo:
                skipped_missing += 1
                continue

            # Generate component key
            repo_name_safe = scan_info["repo_full_name"].replace("/", "_")
            component_key = f"{repo_name_safe}_{scenario_id[:8]}_{scan_info['commit_sha'][:12]}"

            # Check if project already exists on SonarQube server
            if sonar_tool._project_exists(component_key):
                logger.info(
                    f"{corr_prefix} Component {component_key} exists on SonarQube, "
                    "triggering metrics export directly"
                )
                # Trigger metrics export instead of full scan
                from app.tasks.sonar import export_metrics_from_webhook

                export_metrics_from_webhook.delay(
                    component_key=component_key,
                    analysis_status="SUCCESS",
                )
                skipped_exists_on_server += 1
                continue

            # Reset scan status
            sonar_repo.increment_retry(scan_id)

            # Dispatch to SonarQube scan task
            start_sonar_scan_for_version_commit.delay(
                scenario_id=scenario_id,
                commit_sha=scan_info["commit_sha"],
                repo_full_name=scan_info["repo_full_name"],
                raw_repo_id=raw_repo_id,
                github_repo_id=raw_repo.github_repo_id,
                component_key=component_key,
                config_file_path=None,
                correlation_id=correlation_id,
            )
            dispatched += 1

    logger.info(
        f"{corr_prefix} [retry_batch] Batch {batch_index + 1} complete: "
        f"dispatched={dispatched}, skipped_db={skipped_completed}, "
        f"skipped_server={skipped_exists_on_server}, skipped_missing={skipped_missing}"
    )

    return {
        "status": "completed",
        "batch_index": batch_index,
        "dispatched": dispatched,
        "skipped_completed": skipped_completed,
        "skipped_exists_on_server": skipped_exists_on_server,
        "skipped_missing": skipped_missing,
    }

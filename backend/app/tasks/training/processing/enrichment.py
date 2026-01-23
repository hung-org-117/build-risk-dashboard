"""
Training Processing - Enrichment Tasks.

Contains:
- dispatch_scans_and_processing: Dispatch scans + enrichment
- dispatch_enrichment_batches: Create EnrichmentBuild, dispatch chain
- process_single_enrichment: Process single build for feature extraction
- handle_processing_chain_error: Error handler for chain failures
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chain

from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.shared.events import (
    publish_scenario_processing_updated,
    publish_scenario_updated,
)
from app.tasks.training.processing.base import ScenarioProcessingTask
from app.tasks.training.processing.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.dispatch_scans_and_processing",
    queue="scenario_processing",
    soft_time_limit=120,
    time_limit=180,
)
def dispatch_scans_and_processing(
    self: SafeTask,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Dispatch scans (async, fire & forget) and processing after ingestion completes.

    Scans run independently without blocking feature extraction.
    Scan results are backfilled to FeatureVector.scan_metrics later.
    """
    # Import here to avoid circular imports
    from app.tasks.training.processing.scans import dispatch_scenario_scans

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(
            f"{corr_prefix} [dispatch_scans_and_processing] Starting for {scenario_id}"
        )

        scenario_repo = TrainingScenarioRepository(self.db)
        scenario = scenario_repo.find_by_id(scenario_id)

        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Get scan_metrics config from feature_config
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            scan_metrics_config = feature_config.get("scan_metrics", {})
        else:
            scan_metrics_config = getattr(feature_config, "scan_metrics", {}) or {}

        has_scans = bool(scan_metrics_config.get("sonarqube")) or bool(
            scan_metrics_config.get("trivy")
        )

        # Dispatch scans
        if has_scans:
            logger.info(f"{corr_prefix} Dispatching scans in parallel")
            dispatch_scenario_scans.delay(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
            )

        # Dispatch enrichment batches for feature extraction
        dispatch_enrichment_batches.delay(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        return {
            "status": "dispatched",
            "scans_dispatched": has_scans,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.dispatch_enrichment_batches",
    queue="scenario_processing",
    soft_time_limit=180,
    time_limit=240,
)
def dispatch_enrichment_batches(
    self: SafeTask,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Dispatch enrichment processing for INGESTED builds.

    Flow:
    1. Get INGESTED IngestionBuild records
    2. Create EnrichmentBuild for each (if not exists)
    3. Dispatch sequential chain for temporal feature support
    """
    # Import here to avoid circular imports
    from app.tasks.training.processing.finalize import (
        finalize_feature_extraction,
        handle_processing_chain_error,
    )

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))
        # Notify failure
        from app.services.notification_service import notify_training_scenario_failed

        notify_training_scenario_failed(
            db=self.db,
            scenario_id=scenario_id,
            error_message=str(e),
            completed_count=0,
            failed_count=0,
        )

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(
            f"{corr_prefix} [dispatch_enrichment_batches] Starting for {scenario_id}"
        )

        scenario_repo = TrainingScenarioRepository(self.db)
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
        enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Single aggregation query: filters, joins raw_build_runs, sorts by run_created_at
        # Eliminates: 2 separate queries, N+1 pattern, Python-side sorting
        builds_with_raw_data = ingestion_build_repo.find_for_enrichment_with_raw_data(
            scenario_id=scenario_id,
            statuses=[IngestionStatus.INGESTED, IngestionStatus.MISSING_RESOURCE],
        )

        if not builds_with_raw_data:
            logger.warning(f"{corr_prefix} No builds to process")
            updated_scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "status": ScenarioStatus.PROCESSED.value,
                        "processing_completed_at": datetime.utcnow(),
                        "feature_extraction_completed": True,
                    }
                },
                return_updated=True,
            )
            if updated_scenario:
                publish_scenario_updated(updated_scenario)
            return {"status": "completed", "builds_features_extracted": 0}

        # Create EnrichmentBuild records - data already sorted by run_created_at from DB
        enrichment_build_ids = []
        for build_doc in builds_with_raw_data:
            # Determine outcome from conclusion (already joined from raw_build_runs)
            conclusion = build_doc.get("conclusion")
            if conclusion:
                outcome = 1 if conclusion.lower() == "failure" else 0
            else:
                outcome = (
                    1 if "failure" in str(build_doc.get("status", "")).lower() else 0
                )

            eb = enrichment_build_repo.upsert_for_ingestion_build(
                scenario_id=scenario_id,
                ingestion_build_id=str(build_doc["_id"]),
                raw_repo_id=str(build_doc["raw_repo_id"]),
                raw_build_run_id=str(build_doc["raw_build_run_id"]),
                ci_run_id=build_doc.get("ci_run_id", ""),
                commit_sha=build_doc.get("commit_sha", ""),
                repo_full_name=build_doc.get("repo_full_name", ""),
                outcome=outcome,
                build_started_at=build_doc.get("run_started_at"),
            )
            enrichment_build_ids.append(str(eb.id))

        logger.info(
            f"{corr_prefix} Created {len(enrichment_build_ids)} enrichment builds"
        )

        # Get selected features from feature_config
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            dag_features = feature_config.get("dag_features", [])
        else:
            dag_features = getattr(feature_config, "dag_features", []) or []

        selected_features = dag_features if dag_features else []

        logger.info(
            f"{corr_prefix} Selected features: {len(selected_features)} features"
        )

        # Build sequential processing chain
        processing_tasks = [
            process_single_enrichment.si(
                scenario_id=scenario_id,
                enrichment_build_id=build_id,
                selected_features=selected_features,
                correlation_id=correlation_id,
            )
            for build_id in enrichment_build_ids
        ]

        # Chain: B1 → B2 → ... → finalize
        workflow = chain(
            *processing_tasks,
            finalize_feature_extraction.si(
                scenario_id=scenario_id,
                created_count=len(enrichment_build_ids),
                correlation_id=correlation_id,
            ),
        )

        # Error callback for chain failure
        error_callback = handle_processing_chain_error.s(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )
        workflow.on_error(error_callback)
        workflow.apply_async()

        logger.info(
            f"{corr_prefix} Dispatched {len(processing_tasks)} builds for processing"
        )

        publish_scenario_updated(scenario)

        return {
            "status": "dispatched",
            "enrichment_builds_created": len(enrichment_build_ids),
            "total_builds": len(processing_tasks),
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=ScenarioProcessingTask,
    name="app.tasks.training_processing.process_single_enrichment",
    queue="scenario_processing",
    soft_time_limit=300,
    time_limit=600,
)
def process_single_enrichment(
    self: ScenarioProcessingTask,
    scenario_id: str,
    enrichment_build_id: str,
    selected_features: List[str],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Process a single enrichment build for feature extraction.

    Uses extract_features_for_build helper with Hamilton DAG.
    """
    from app.entities.feature_audit_log import AuditLogCategory
    from app.tasks.shared import extract_features_for_build

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    scenario_repo = TrainingScenarioRepository(self.db)
    enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    # Load enrichment build
    enrichment_build = enrichment_build_repo.find_by_id(enrichment_build_id)
    if not enrichment_build:
        logger.error(f"{corr_prefix} EnrichmentBuild {enrichment_build_id} not found")
        return {"status": "error", "error": "EnrichmentBuild not found"}

    if enrichment_build.extraction_status == ExtractionStatus.COMPLETED.value:
        return {"status": "skipped", "reason": "already_processed"}

    # Load dependencies
    raw_build_run = raw_build_run_repo.find_by_id(enrichment_build.raw_build_run_id)
    if not raw_build_run:
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message="RawBuildRun not found",
        )
        return {"status": "failed", "error": "RawBuildRun not found"}

    raw_repo = raw_repo_repo.find_by_id(raw_build_run.raw_repo_id)
    if not raw_repo:
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message="RawRepository not found",
        )
        return {"status": "failed", "error": "RawRepository not found"}

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    def _mark_failed(exc: Exception) -> None:
        """Mark build as FAILED and update stats."""
        error_msg = str(exc)
        logger.error(f"{corr_prefix} Error for {enrichment_build_id}: {error_msg}")
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message=error_msg,
        )
        scenario_repo.increment_counter(scenario_id, "builds_features_extracted_failed")

        publish_scenario_processing_updated(
            scenario_id=scenario_id,
            build_id=enrichment_build_id,
            extraction_status="failed",
            error=error_msg,
            ci_run_id=str(raw_build_run.ci_run_id) if raw_build_run else None,
            commit_sha=raw_build_run.commit_sha if raw_build_run else None,
            repo_full_name=raw_repo.full_name if raw_repo else None,
            enriched_at=datetime.utcnow().isoformat(),
        )

    def _work(state: TaskState) -> Dict[str, Any]:
        """Feature extraction work function."""
        # Mark as in progress
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.IN_PROGRESS,
        )

        # Extract features using Hamilton DAG
        result = extract_features_for_build(
            db=self.db,
            raw_repo=raw_repo,
            feature_config={},
            raw_build_run=raw_build_run,
            selected_features=selected_features,
            output_build_id=enrichment_build_id,
            category=AuditLogCategory.TRAINING_SCENARIO,
            scenario_id=scenario_id,
        )

        # Update enrichment build with result
        if result["status"] == "completed":
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.COMPLETED,
                feature_vector_id=result.get("feature_vector_id"),
            )
        elif result["status"] == "partial":
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.PARTIAL,
                feature_vector_id=result.get("feature_vector_id"),
                error_message="; ".join(result.get("errors", [])),
            )
        else:
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.FAILED,
                error_message="; ".join(result.get("errors", [])),
            )

        # Increment processed count
        scenario_repo.increment_counter(scenario_id, "builds_features_extracted")

        # Get expected feature count from scenario config
        expected_feature_count = len(selected_features) if selected_features else 0

        # Publish event for real-time UI update with enriched payload
        publish_scenario_processing_updated(
            scenario_id=scenario_id,
            build_id=enrichment_build_id,
            extraction_status=result["status"],
            feature_count=result.get("feature_count", 0),
            expected_feature_count=expected_feature_count,
            ci_run_id=str(raw_build_run.ci_run_id) if raw_build_run else None,
            commit_sha=raw_build_run.commit_sha if raw_build_run else None,
            repo_full_name=raw_repo.full_name if raw_repo else None,
            enriched_at=datetime.utcnow().isoformat(),
            error="; ".join(result.get("errors", [])) if result.get("errors") else None,
        )

        # Publish aggregate scenario update for real-time progress bar
        updated_scenario = scenario_repo.find_by_id(scenario_id)
        if updated_scenario:
            publish_scenario_updated(updated_scenario)

        logger.info(
            f"{corr_prefix} [process_single] {enrichment_build_id}: "
            f"status={result['status']}, features={result.get('feature_count', 0)}"
        )

        return {
            "status": result["status"],
            "build_id": enrichment_build_id,
            "feature_count": result.get("feature_count", 0),
        }

    return self.run_safe(
        job_id=enrichment_build_id,
        work=_work,
        mark_failed_fn=_mark_failed,
    )

"""
Training Pipeline - Processing Tasks (Phase 2)

This module handles the processing phase of training scenario (user-triggered):
1. start_scenario_processing - Entry point: User triggers after reviewing ingestion
2. dispatch_scans_and_processing - Dispatch scans (async) + feature extraction
3. dispatch_enrichment_batches - Create EnrichmentBuild + dispatch sequential chain
4. process_single_enrichment - Process single build for feature extraction
5. finalize_feature_extraction - Finalize after all feature extraction completed
6. reprocess_failed_builds - Retry FAILED enrichment builds

Note: Dataset generation tasks moved to app.tasks.training_export module.
"""

from app.entities import TrainingIngestionBuild
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
from app.tasks.base import PipelineTask, SafeTask, ScenarioProcessingTask, TaskState
from app.tasks.shared.events import (
    publish_scenario_processing_updated,
    publish_scenario_updated,
)

logger = logging.getLogger(__name__)


def _create_scenario_failure_handler(scenario_id: str, db):
    """
    Create a failure handler for TrainingScenario tasks.
    Updates status to FAILED on unhandled errors.
    """

    def handler(status: str, error_message: str) -> None:
        try:
            scenario_repo = TrainingScenarioRepository(db)
            updated_scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "status": ScenarioStatus.FAILED.value,
                        "error_message": error_message,
                    }
                },
                return_updated=True,
            )
            if updated_scenario:
                publish_scenario_updated(updated_scenario, error=error_message)
        except Exception as e:
            logger.warning(f"Failed to update scenario {scenario_id}: {e}")

    return handler


# PHASE 2: PROCESSING (User-Triggered)
@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.start_scenario_processing",
    queue="scenario_processing",
    soft_time_limit=60,
    time_limit=120,
)
def start_scenario_processing(
    self: SafeTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Phase 2: Start processing phase (manually triggered by user).

    Validates that ingestion is complete before starting feature extraction.
    Only proceeds if status is INGESTED.
    """

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        import uuid

        correlation_id = str(uuid.uuid4())
        logger.info(f"[start_scenario_processing] Starting for scenario {scenario_id}")

        scenario_repo = TrainingScenarioRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Validate status
        if scenario.status != ScenarioStatus.INGESTED.value:
            return {
                "status": "error",
                "error": f"Cannot start processing: status is {scenario.status}, expected INGESTED",
            }

        # Update status to PROCESSING atomically and get updated document
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSING.value,
                    "processing_started_at": datetime.utcnow(),
                    "current_task_id": self.request.id,
                }
            },
            return_updated=True,
        )

        if scenario:
            publish_scenario_updated(scenario)

        # Dispatch scans and processing
        dispatch_scans_and_processing.delay(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        return {
            "status": "dispatched",
            "scenario_id": scenario_id,
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

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
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

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
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
        raw_build_run_repo = RawBuildRunRepository(self.db)

        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Get INGESTED + MISSING_RESOURCE builds (both can be processed)
        ingested_builds, _ = ingestion_build_repo.find_by_scenario(
            scenario_id, status_filter=IngestionStatus.INGESTED
        )
        missing_resource_builds, _ = ingestion_build_repo.find_by_scenario(
            scenario_id, status_filter=IngestionStatus.MISSING_RESOURCE
        )

        all_builds = ingested_builds + missing_resource_builds

        if not all_builds:
            logger.warning(f"{corr_prefix} No builds to process")
            # No builds - mark as PROCESSED (user can still generate empty dataset)
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

        # Get raw build run data for outcome determination and temporal ordering
        raw_build_run_ids = [b.raw_build_run_id for b in all_builds]
        raw_build_runs = {
            str(r.id): r
            for r in [raw_build_run_repo.find_by_id(rid) for rid in raw_build_run_ids]
            if r is not None
        }

        # Sort by build creation time (oldest first) for temporal features
        def get_build_timestamp(b: TrainingIngestionBuild):
            raw_run = raw_build_runs.get(str(b.raw_build_run_id))
            if raw_run and raw_run.run_created_at:
                return raw_run.run_created_at
            if b.created_at:
                return b.created_at
            return datetime.utcnow()

        all_builds.sort(key=get_build_timestamp)

        # Create EnrichmentBuild records
        enrichment_build_ids = []
        for build in all_builds:
            raw_run = raw_build_runs.get(str(build.raw_build_run_id))

            # Determine outcome from conclusion
            if raw_run and raw_run.conclusion:
                outcome = 1 if raw_run.conclusion.lower() == "failure" else 0
            else:
                outcome = 1 if "failure" in str(build.status).lower() else 0

            eb = enrichment_build_repo.upsert_for_ingestion_build(
                scenario_id=scenario_id,
                ingestion_build_id=str(build.id),
                raw_repo_id=str(build.raw_repo_id),
                raw_build_run_id=str(build.raw_build_run_id),
                ci_run_id=build.ci_run_id,
                commit_sha=build.commit_sha,
                repo_full_name=build.repo_full_name,
                outcome=outcome,
                build_started_at=raw_run.run_started_at if raw_run else None,
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

        # Expand wildcard patterns
        selected_features = _expand_feature_patterns(dag_features)

        logger.info(
            f"{corr_prefix} Patterns: {dag_features}, expanded: {len(selected_features)} features"
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
    base=PipelineTask,
    name="app.tasks.training_processing.handle_processing_chain_error",
    queue="scenario_processing",
    soft_time_limit=60,
    time_limit=120,
)
def handle_processing_chain_error(
    self: PipelineTask,
    request,
    exc,
    traceback,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Error callback for processing chain failure.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    error_msg = str(exc) if exc else "Unknown processing error"

    logger.error(
        f"{corr_prefix} Processing chain failed for {scenario_id}: {error_msg}"
    )

    enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)
    scenario_repo = TrainingScenarioRepository(self.db)

    now = datetime.utcnow()

    # Mark all IN_PROGRESS enrichment builds as FAILED
    failed_count = enrichment_build_repo.collection.update_many(
        {
            "scenario_id": ObjectId(scenario_id),
            "extraction_status": ExtractionStatus.IN_PROGRESS.value,
        },
        {
            "$set": {
                "extraction_status": ExtractionStatus.FAILED.value,
                "extraction_error": f"Chain failed: {error_msg}",
            }
        },
    ).modified_count

    # Count completed builds
    completed_count = enrichment_build_repo.collection.count_documents(
        {
            "scenario_id": ObjectId(scenario_id),
            "extraction_status": ExtractionStatus.COMPLETED.value,
        }
    )

    if completed_count > 0:
        # Some builds completed - mark as PROCESSED (user triggers split manually)
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSED.value,
                    "builds_features_extracted": completed_count,
                    "builds_features_extracted_failed": failed_count,
                    "processing_completed_at": now,
                    "feature_extraction_completed": True,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario)

        # Check and notify enrichment completion (if scans also done)
        from app.services.notification_service import (
            check_and_notify_enrichment_completed,
        )

        check_and_notify_enrichment_completed(self.db, scenario_id)
    else:
        # No builds completed - mark as FAILED and notify
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.FAILED.value,
                    "error_message": error_msg,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario, error=error_msg)

        # Notify failure
        from app.services.notification_service import notify_training_scenario_failed

        notify_training_scenario_failed(
            db=self.db,
            scenario_id=scenario_id,
            error_message=error_msg,
            completed_count=completed_count,
            failed_count=failed_count,
        )

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "completed_builds": completed_count,
        "error": error_msg,
    }


@celery_app.task(
    bind=True,
    base=ScenarioProcessingTask,
    name="app.tasks.training_processing.process_single_enrichment",
    queue="scenario_processing",
    soft_time_limit=300,
    time_limit=600,
    max_retries=0,
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


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_processing.finalize_feature_extraction",
    queue="scenario_processing",
    soft_time_limit=160,
    time_limit=220,
)
def finalize_feature_extraction(
    self: SafeTask,
    scenario_id: str,
    created_count: int = 0,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Finalize feature extraction phase after all builds have been processed.

    Marks feature_extraction_completed=True. Scenario stays in PROCESSED status.
    Scans may still be running in parallel.
    """

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(f"{corr_prefix} [finalize_processing] Finalizing for {scenario_id}")

        scenario_repo = TrainingScenarioRepository(self.db)
        enrichment_build_repo = TrainingEnrichmentBuildRepository(self.db)

        # Get stats
        stats = enrichment_build_repo.aggregate_stats_by_scenario(scenario_id)
        completed = stats.get("completed", 0)
        partial = stats.get("partial", 0)
        failed = stats.get("failed", 0)
        total = completed + partial + failed

        # Update scenario - mark as PROCESSED (user triggers split manually)

        # Publish update to UI
        # Use atomic find_one_and_update to update status and get the final document
        updated_scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.PROCESSED.value,
                    "builds_features_extracted": completed + partial,
                    "builds_features_extracted_failed": failed,
                    "processing_completed_at": datetime.utcnow(),
                    "feature_extraction_completed": True,
                }
            },
            return_updated=True,
        )

        if updated_scenario:
            publish_scenario_updated(updated_scenario)

            logger.info(
                f"{corr_prefix} Completed: {completed + partial}/{total}, failed: {failed}. "
            )

            # Trigger quality evaluation immediately after feature extraction
            try:
                from app.services.data_quality_service import DataQualityService

                quality_service = DataQualityService(self.db)
                quality_service.finalize_quality_report(scenario_id)
                logger.info(f"{corr_prefix} Quality report finalized for {scenario_id}")
            except Exception as e:
                logger.warning(f"{corr_prefix} Quality evaluation failed: {e}")

            # Check if enrichment is fully complete (features + scans) and send notification
            from app.services.notification_service import (
                check_and_notify_enrichment_completed,
            )

            check_and_notify_enrichment_completed(self.db, scenario_id)

            return {
                "status": "completed",
                "builds_features_extracted": completed + partial,
                "builds_features_extracted_failed": failed,
                "total": total,
            }

        return {"status": "error", "error": "Scenario not found"}

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=ScenarioProcessingTask,
    name="app.tasks.training_processing.reprocess_failed_feature_extraction",
    queue="scenario_processing",
    soft_time_limit=300,
    time_limit=360,
    max_retries=0,  # Disable retries - fail fast on timeout
)
def reprocess_failed_feature_extraction(
    self: ScenarioProcessingTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Reprocess only FAILED enrichment builds for a scenario.

    Uses sequential chain to ensure temporal features work correctly.
    """

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
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
        selected_features = _expand_feature_patterns(dag_features)

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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


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

        # Chain batches - use .si() (immutable) to prevent previous task's result
        # from being passed as first positional argument
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
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(f"{corr_prefix} [scan_batch] Batch {batch_index + 1}/{total_batches}")

    from app.tasks.training_scan_helpers import dispatch_scan_for_scenario_commit

    dispatched = 0
    for commit_info in commits_batch:
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
        scans_to_retry[i : i + batch_size]
        for i in range(0, len(scans_to_retry), batch_size)
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
                logger.debug(
                    f"{corr_prefix} Skip {scan_info['commit_sha'][:8]} - completed in DB"
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

            # Generate component key (repo + commit only)
            repo_name_safe = scan_info["repo_full_name"].replace("/", "_")
            component_key = f"{repo_name_safe}_{scan_info['commit_sha'][:12]}"

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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _expand_feature_patterns(patterns: List[str]) -> List[str]:
    """Expand wildcard feature patterns to actual feature names."""
    from app.tasks.pipeline.feature_dag._feature_definitions import FEATURE_REGISTRY

    if not patterns:
        return list(FEATURE_REGISTRY.keys())

    expanded = set()
    for pattern in patterns:
        if "*" in pattern:
            prefix = pattern.replace("*", "")
            for feature_name in FEATURE_REGISTRY.keys():
                if feature_name.startswith(prefix):
                    expanded.add(feature_name)
        else:
            if pattern in FEATURE_REGISTRY:
                expanded.add(pattern)

    return list(expanded) if expanded else list(FEATURE_REGISTRY.keys())

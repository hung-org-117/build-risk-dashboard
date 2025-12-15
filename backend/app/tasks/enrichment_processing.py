"""
Version Enrichment Tasks - Chain+Group pattern for parallel feature extraction.

Flow:
1. start_enrichment - Orchestrator: Dispatch ingestion then enrichment
2. start_ingestion_for_version - Run ingestion for repos with selected features
3. dispatch_enrichment_batches - After ingestion, dispatch batch processing
4. process_enrichment_batch - Process a batch of builds for feature extraction
5. finalize_enrichment - Mark version as completed
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from bson import ObjectId
from celery import chain, chord, group

from app.celery_app import celery_app
from app.config import settings
from app.paths import REPOS_DIR
from app.entities.dataset_build import DatasetBuild
from app.entities.enums import ExtractionStatus
from app.entities.dataset_enrichment_build import DatasetEnrichmentBuild
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dataset_version import DatasetVersionRepository
from app.repositories.dataset_build_repository import DatasetBuildRepository
from app.repositories.dataset_enrichment_build import DatasetEnrichmentBuildRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.dataset_repo_config import DatasetRepoConfigRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import PipelineTask
from app.tasks.shared import extract_features_for_build

logger = logging.getLogger(__name__)


# Task 1: Orchestrator - starts ingestion then enrichment
@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.version_enrichment.start_enrichment",
    queue="processing",
)
def start_enrichment(self: PipelineTask, version_id: str) -> Dict[str, Any]:
    """
    Orchestrator: Start ingestion for version, then dispatch enrichment.

    Flow: start_enrichment -> start_ingestion_for_version -> dispatch_enrichment_batches
          -> chord([process_enrichment_batch x N]) -> finalize_enrichment
    """
    version_repo = DatasetVersionRepository(self.db)
    dataset_build_repo = DatasetBuildRepository(self.db)
    dataset_repo = DatasetRepository(self.db)
    repo_config_repo = DatasetRepoConfigRepository(self.db)

    # Load version
    version = version_repo.find_by_id(version_id)
    if not version:
        logger.error(f"Version {version_id} not found")
        return {"status": "error", "error": "Version not found"}

    # Mark as started
    version_repo.mark_started(version_id, task_id=self.request.id)

    try:
        # Load dataset
        dataset = dataset_repo.find_by_id(version.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {version.dataset_id} not found")

        # Get validated builds
        validated_builds = dataset_build_repo.find_validated_builds(version.dataset_id)

        total_rows = len(validated_builds)
        if total_rows == 0:
            raise ValueError("No validated builds found. Please run validation first.")

        # Get repos for this dataset
        repos = repo_config_repo.find_by_dataset(version.dataset_id)

        version_repo.update_one(
            version_id,
            {
                "total_rows": total_rows,
                "repos_total": len(repos),
                "ingestion_status": "ingesting",
            },
        )
        logger.info(
            f"Found {total_rows} validated builds, {len(repos)} repos to ingest"
        )

        # Dispatch ingestion first, then enrichment
        # Chain: ingestion -> dispatch_enrichment_batches
        workflow = chain(
            start_ingestion_for_version.s(version_id=version_id),
            dispatch_enrichment_batches.s(version_id=version_id),
        )
        workflow.apply_async()

        return {
            "status": "dispatched",
            "total_builds": total_rows,
            "repos": len(repos),
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Version enrichment start failed: {error_msg}")
        version_repo.mark_failed(version_id, error_msg)
        raise


# Task 1b: Run ingestion for version repos
@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.version_enrichment.start_ingestion_for_version",
    queue="ingestion",
    soft_time_limit=600,
    time_limit=900,
)
def start_ingestion_for_version(self: PipelineTask, version_id: str) -> Dict[str, Any]:
    """
    Run ingestion for all repos in a version with selected features.

    This is a synchronous task that dispatches per-repo ingestion tasks
    and waits for them to complete before returning.
    """
    from app.tasks.dataset_ingestion import ingest_dataset_builds

    version_repo = DatasetVersionRepository(self.db)
    repo_config_repo = DatasetRepoConfigRepository(self.db)
    build_repo = DatasetBuildRepository(self.db)

    version = version_repo.find_by_id(version_id)
    if not version:
        raise ValueError(f"Version {version_id} not found")

    # Get repos
    repos = repo_config_repo.find_by_dataset(version.dataset_id)
    if not repos:
        version_repo.update_one(
            version_id,
            {"ingestion_status": "completed", "ingestion_progress": 100},
        )
        return {"status": "completed", "message": "No repos to ingest"}

    repos_ingested = 0
    repos_failed = 0

    for i, repo in enumerate(repos):
        repo_id = str(repo.id)

        # Get validated builds for this repo
        builds = build_repo.find_by_repo(version.dataset_id, repo_id)
        build_ids = [str(b.build_id_from_csv) for b in builds if b.status == "found"]

        if not build_ids:
            continue

        try:
            # Run ingestion synchronously for this repo
            result = ingest_dataset_builds.apply(
                kwargs={
                    "dataset_id": version.dataset_id,
                    "repo_id": repo_id,
                    "build_ids": build_ids,
                    "features": version.selected_features,
                }
            )

            if result.successful():
                repos_ingested += 1
            else:
                repos_failed += 1
                logger.error(f"Ingestion failed for repo {repo.normalized_full_name}")

        except Exception as e:
            repos_failed += 1
            logger.error(f"Ingestion error for repo {repo.normalized_full_name}: {e}")

        # Update progress
        progress = int(((i + 1) / len(repos)) * 100)
        version_repo.update_one(
            version_id,
            {
                "ingestion_progress": progress,
                "repos_ingested": repos_ingested,
                "repos_failed": repos_failed,
            },
        )

    # Mark ingestion complete
    version_repo.update_one(
        version_id,
        {"ingestion_status": "completed", "ingestion_progress": 100},
    )

    logger.info(
        f"Ingestion completed for version {version_id}: "
        f"{repos_ingested} succeeded, {repos_failed} failed"
    )

    return {
        "status": "completed",
        "repos_ingested": repos_ingested,
        "repos_failed": repos_failed,
    }


# Task 1c: Dispatch enrichment batches after ingestion
@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.version_enrichment.dispatch_enrichment_batches",
    queue="processing",
)
def dispatch_enrichment_batches(
    self: PipelineTask, ingestion_result: Dict[str, Any], version_id: str
) -> Dict[str, Any]:
    """
    After ingestion completes, dispatch enrichment batches.
    """
    version_repo = DatasetVersionRepository(self.db)
    dataset_build_repo = DatasetBuildRepository(self.db)

    version = version_repo.find_by_id(version_id)
    if not version:
        raise ValueError(f"Version {version_id} not found")

    # Get validated builds
    validated_builds = dataset_build_repo.find_validated_builds(version.dataset_id)
    build_ids = [str(build.id) for build in validated_builds]

    if not build_ids:
        version_repo.mark_completed(version_id)
        return {"status": "completed", "message": "No builds to process"}

    # Split into batches
    batch_size = settings.ENRICHMENT_BATCH_SIZE
    batches = [
        build_ids[i : i + batch_size] for i in range(0, len(build_ids), batch_size)
    ]

    logger.info(
        f"Dispatching {len(batches)} batches of {batch_size} builds for enrichment"
    )

    # Create tasks for each batch
    batch_tasks = [
        process_enrichment_batch.s(
            version_id=version_id,
            build_ids=batch,
            selected_features=version.selected_features,
            batch_index=i,
            total_batches=len(batches),
        )
        for i, batch in enumerate(batches)
    ]

    # Use chord to run all batches in parallel, then finalize
    chord(group(batch_tasks))(finalize_enrichment.s(version_id=version_id))

    return {
        "status": "dispatched",
        "batches": len(batches),
        "total_builds": len(build_ids),
    }


# Task 2: Process batch
@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.version_enrichment.process_enrichment_batch",
    queue="processing",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.ENRICHMENT_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    soft_time_limit=600,
    time_limit=900,
)
def process_enrichment_batch(
    self: PipelineTask,
    version_id: str,
    build_ids: List[str],
    selected_features: List[str],
    batch_index: int,
    total_batches: int,
) -> Dict[str, Any]:
    """
    Process a batch of builds for feature extraction.

    Returns stats for this batch to be aggregated by finalize_enrichment.
    """
    version_repo = DatasetVersionRepository(self.db)
    dataset_build_repo = DatasetBuildRepository(self.db)
    enrichment_build_repo = DatasetEnrichmentBuildRepository(self.db)
    build_run_repo = RawBuildRunRepository(self.db)
    enrichment_repo_repo = DatasetRepoConfigRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    version = version_repo.find_by_id(version_id)
    if not version:
        return {"status": "error", "error": "Version not found"}

    enriched = 0
    failed = 0

    for build_id in build_ids:
        build = dataset_build_repo.find_by_id(build_id)
        if not build:
            logger.warning(f"Build {build_id} not found")
            failed += 1
            continue

        try:
            result = _extract_features_for_enrichment(
                db=self.db,
                build=build,
                selected_features=selected_features,
                build_run_repo=build_run_repo,
                enrichment_repo_repo=enrichment_repo_repo,
                raw_repo_repo=raw_repo_repo,
            )

            # Determine extraction status from result
            if result["status"] == "completed":
                extraction_status = ExtractionStatus.COMPLETED
            elif result["status"] == "failed":
                extraction_status = ExtractionStatus.FAILED
            else:
                extraction_status = ExtractionStatus.PENDING

            features = result["features"]
            extraction_error = result["errors"][0] if result["errors"] else None

            # Update or create enrichment_build
            existing = enrichment_build_repo.find_by_csv_build_id(
                ObjectId(version.dataset_id), build.build_id_from_csv
            )
            if existing and existing.id:
                enrichment_build_repo.save_features(
                    existing.id,
                    features,
                )
                enrichment_build_repo.update_extraction_status(
                    existing.id,
                    extraction_status,
                    error=extraction_error,
                )
            else:
                enrichment_build = DatasetEnrichmentBuild(
                    _id=None,
                    raw_repo_id=ObjectId(build.repo_id),
                    raw_workflow_run_id=ObjectId(build.workflow_run_id),
                    dataset_id=ObjectId(version.dataset_id),
                    dataset_version_id=ObjectId(version_id),
                    dataset_repo_config_id=None,
                    build_id_from_csv=build.build_id_from_csv,
                    csv_row_index=0,
                    csv_row_data=None,
                    head_sha=None,
                    build_number=None,
                    build_conclusion=None,
                    build_created_at=None,
                    extraction_status=extraction_status,
                    extraction_error=extraction_error,
                    features=features,
                    enriched_at=None,
                )
                enrichment_build_repo.insert_one(enrichment_build)

            if result["status"] == "completed":
                enriched += 1
            else:
                failed += 1

        except Exception as e:
            logger.warning(f"Failed to enrich build {build.build_id_from_csv}: {e}")

            existing = enrichment_build_repo.find_by_csv_build_id(
                ObjectId(version.dataset_id), build.build_id_from_csv
            )
            if not existing:
                enrichment_build = DatasetEnrichmentBuild(
                    _id=None,
                    raw_repo_id=ObjectId(build.repo_id),
                    raw_workflow_run_id=ObjectId(build.workflow_run_id),
                    dataset_id=ObjectId(version.dataset_id),
                    dataset_version_id=ObjectId(version_id),
                    dataset_repo_config_id=None,
                    build_id_from_csv=build.build_id_from_csv,
                    csv_row_index=0,
                    csv_row_data=None,
                    head_sha=None,
                    build_number=None,
                    build_conclusion=None,
                    build_created_at=None,
                    extraction_status=ExtractionStatus.PENDING,
                    extraction_error=str(e),
                    enriched_at=None,
                    features={},
                )
                enrichment_build_repo.insert_one(enrichment_build)
            elif existing.id:
                enrichment_build_repo.update_extraction_status(
                    existing.id,
                    ExtractionStatus.PENDING,
                    error=str(e),
                )

            failed += 1

    logger.info(
        f"Batch {batch_index + 1}/{total_batches} completed: "
        f"{enriched} enriched, {failed} failed"
    )

    return {
        "batch_index": batch_index,
        "status": "completed",
        "enriched": enriched,
        "failed": failed,
        "total": len(build_ids),
    }


# Task 3: Finalize
@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.version_enrichment.finalize_enrichment",
    queue="processing",
)
def finalize_enrichment(
    self: PipelineTask,
    batch_results: List[Dict[str, Any]],
    version_id: str,
) -> Dict[str, Any]:
    """
    Aggregate results from all batch enrichments and update version status.
    """
    version_repo = DatasetVersionRepository(self.db)

    # Aggregate stats
    total_enriched = 0
    total_failed = 0
    total_processed = 0

    for result in batch_results:
        total_enriched += result.get("enriched", 0)
        total_failed += result.get("failed", 0)
        total_processed += result.get("total", 0)

    # Update final progress
    version_repo.update_progress(
        version_id,
        processed_rows=total_processed,
        enriched_rows=total_enriched,
        failed_rows=total_failed,
    )

    # Mark completed
    version_repo.mark_completed(version_id)

    logger.info(
        f"Version enrichment completed: {version_id}, "
        f"{total_enriched}/{total_processed} rows enriched"
    )

    return {
        "status": "completed",
        "version_id": version_id,
        "enriched_rows": total_enriched,
        "failed_rows": total_failed,
        "total_rows": total_processed,
    }


def _extract_features_for_enrichment(
    db,
    build: DatasetBuild,
    selected_features: List[str],
    build_run_repo: RawBuildRunRepository,
    enrichment_repo_repo: DatasetRepoConfigRepository,
    raw_repo_repo: RawRepositoryRepository,
) -> Dict[str, Any]:
    """
    Extract features for a single build using shared helper.

    Returns result dict with status, features, errors, warnings.
    """
    if not build.workflow_run_id:
        logger.warning(f"Build {build.build_id_from_csv} has no workflow_run_id")
        return {
            "status": "failed",
            "features": {},
            "errors": ["No workflow_run_id"],
            "warnings": [],
        }

    build_run = build_run_repo.find_by_id(str(build.workflow_run_id))
    if not build_run:
        logger.warning(f"BuildRun {build.workflow_run_id} not found")
        return {
            "status": "failed",
            "features": {},
            "errors": ["BuildRun not found"],
            "warnings": [],
        }

    enrichment_repo = enrichment_repo_repo.find_by_id(str(build.repo_id))
    if not enrichment_repo:
        logger.warning(f"EnrichmentRepo {build.repo_id} not found")
        return {
            "status": "failed",
            "features": {},
            "errors": ["EnrichmentRepo not found"],
            "warnings": [],
        }

    raw_repo = raw_repo_repo.find_by_id(str(build.repo_id))
    if not raw_repo:
        logger.warning(f"RawRepository {build.repo_id} not found")
        return {
            "status": "failed",
            "features": {},
            "errors": ["RawRepository not found"],
            "warnings": [],
        }

    # Use shared helper for feature extraction (returns full result with status)
    return extract_features_for_build(
        db=db,
        raw_repo=raw_repo,
        repo_config=enrichment_repo,
        build_run=build_run,
        selected_features=selected_features,
    )

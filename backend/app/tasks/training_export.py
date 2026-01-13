"""
Training Pipeline - Export Tasks (Phase 3)

This module handles the export phase for TrainingDatasetExport entities.
Each export creates train/val/test splits with its own configuration.

Tasks:
1. generate_export_dataset - Generate dataset for a specific export

The key difference from the old flow:
- Scenario ends at PROCESSED status
- Each TrainingDatasetExport has its own splitting/preprocessing/output config
- Multiple exports can be created from one scenario
- **Lazy Materialization**: "master_dataset.parquet" is created only on first export
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app import paths
from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.entities.training_dataset_export import ExportStatus, TrainingDatasetExport
from app.repositories.feature_vector import FeatureVectorRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_dataset_export import TrainingDatasetExportRepository
from app.repositories.training_dataset_split import TrainingDatasetSplitRepository
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.services.splitting_strategy_service import SplittingStrategyService
from app.tasks.base import SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_update

logger = logging.getLogger(__name__)


def _create_export_failure_handler(export_id: str, db):
    """
    Create a failure handler for TrainingDatasetExport tasks.
    Updates status to FAILED on unhandled errors.
    """

    def handler(status: str, error_message: str) -> None:
        try:
            export_repo = TrainingDatasetExportRepository(db)
            export_repo.mark_failed(export_id, error_message)
        except Exception as e:
            logger.warning(f"Failed to update export {export_id}: {e}")

    return handler


# ============================================================================
# EXPORT GENERATION TASK
# ============================================================================


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_export.generate_export_dataset",
    queue="scenario_processing",
    soft_time_limit=600,
    time_limit=720,
)
def generate_export_dataset(
    self: SafeTask,
    scenario_id: str,
    export_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Generate dataset for a TrainingDatasetExport.

    Args:
        scenario_id: Scenario ID (for data retrieval)
        export_id: Export ID (contains split/preprocessing/output config)
        correlation_id: Correlation ID for logging

    Flow:
    1. Validate export exists and scenario is PROCESSED
    2. Lazy Load: Ensure 'master_dataset.parquet' exists (materialize if needed)
    3. Read Master Dataset (fast, from Parquet)
    4. Apply splitting strategy from export config
    5. Export to files (parquet/csv based on output config)
    6. Create TrainingDatasetSplit records
    7. Mark export as COMPLETED
    """

    def mark_failed(e: Exception):
        handler = _create_export_failure_handler(export_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        import uuid

        nonlocal correlation_id

        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(
            f"{corr_prefix} [generate_export] Starting for export {export_id} "
            f"(scenario {scenario_id})"
        )

        # Initialize repositories
        scenario_repo = TrainingScenarioRepository(self.db)
        export_repo = TrainingDatasetExportRepository(self.db)
        split_repo = TrainingDatasetSplitRepository(self.db)

        # Validate export
        export = export_repo.find_by_id(export_id)
        if not export:
            return {"status": "error", "error": "Export not found"}

        # Validate scenario
        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "error": "Scenario not found"}

        # Update export status to GENERATING
        export_repo.update_status(export_id, ExportStatus.GENERATING)

        # ======================================================================
        # STEP 2: Lazy Materialization
        # ======================================================================
        try:
            df = _ensure_dataset_materialized(
                scenario_id, self.db, correlation_id=correlation_id
            )
        except Exception as e:
            logger.error(f"{corr_prefix} Failed to materialize dataset: {e}")
            export_repo.mark_failed(export_id, f"Materialization failed: {str(e)}")
            raise e

        if df.empty:
            logger.warning(f"{corr_prefix} Master dataset is empty")
            export_repo.mark_failed(export_id, "Master dataset is empty")
            return {"status": "error", "error": "Master dataset is empty"}

        logger.info(f"{corr_prefix} Loaded master dataset with {len(df)} rows")

        # ======================================================================
        # STEP 3: Apply Splitting
        # ======================================================================
        splitting_service = SplittingStrategyService()
        splitting_config = export.splitting_config

        result = splitting_service.apply_split(
            df=df,
            config=splitting_config,
            label_column="outcome",
        )

        # ======================================================================
        # STEP 4: Export to Files
        # ======================================================================

        # Delete old splits for this export (if regenerating)
        split_repo.delete_by_export(export_id)

        # Create output directory
        output_dir = paths.get_ml_dataset_dir(scenario_id) / export_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine export formats from output config
        output_config = export.output_config
        export_formats = output_config.formats if output_config.formats else ["parquet"]

        split_stats = {}
        start_time = datetime.utcnow()

        for split_type, indices in [
            ("train", result.train_indices),
            ("validation", result.val_indices),
            ("test", result.test_indices),
        ]:
            if not indices:
                continue

            split_df = df.loc[indices]
            split_stats[split_type] = {"count": len(split_df)}

            # Export in each format
            for fmt in export_formats:
                file_path = output_dir / f"{split_type}.{fmt}"

                export_start = datetime.utcnow()
                if fmt == "parquet":
                    split_df.to_parquet(file_path, index=False)
                else:  # csv
                    split_df.to_csv(file_path, index=False)

                duration = (datetime.utcnow() - export_start).total_seconds()
                file_size = file_path.stat().st_size
                class_dist = split_df["outcome"].value_counts().to_dict()

                split_repo.create_split(
                    export_id=export_id,
                    scenario_id=scenario_id,
                    split_type=split_type,
                    record_count=len(split_df),
                    feature_count=len(split_df.columns),
                    class_distribution={str(k): v for k, v in class_dist.items()},
                    group_distribution={},
                    file_path=str(file_path.relative_to(paths.DATA_DIR)),
                    file_size_bytes=file_size,
                    file_format=fmt,
                    feature_names=list(split_df.columns),
                    generation_duration_seconds=duration,
                )

                split_stats[split_type][fmt] = file_size

        total_duration = (datetime.utcnow() - start_time).total_seconds()

        # Mark export as completed
        export_repo.mark_completed(
            export_id=export_id,
            train_count=len(result.train_indices),
            val_count=len(result.val_indices),
            test_count=len(result.test_indices),
            feature_count=len(df.columns),
            generation_duration_seconds=total_duration,
        )

        # Publish update
        publish_scenario_update(
            scenario_id=scenario_id,
            current_phase=f"Export '{export.name}' completed",
            extra_data={
                "export_id": export_id,
                "train_count": len(result.train_indices),
                "val_count": len(result.val_indices),
                "test_count": len(result.test_indices),
            },
        )

        logger.info(
            f"{corr_prefix} Completed: train={len(result.train_indices)}, "
            f"val={len(result.val_indices)}, test={len(result.test_indices)}"
        )

        return {
            "status": "completed",
            "export_id": export_id,
            "train_count": len(result.train_indices),
            "val_count": len(result.val_indices),
            "test_count": len(result.test_indices),
            "split_stats": split_stats,
            "duration_seconds": total_duration,
        }

    return self.run_safe(
        job_id=export_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


# ============================================================================
# LAZY MATERIALIZATION
# ============================================================================


def _ensure_dataset_materialized(
    scenario_id: str, db, correlation_id: str = ""
) -> pd.DataFrame:
    """
    Ensure 'master_dataset.parquet' exists for the scenario.
    If not, materialize it by streaming data from MongoDB.

    Returns:
        pd.DataFrame: The loaded dataset.
    """
    scenario_dir = paths.get_ml_dataset_dir(scenario_id)
    master_file = scenario_dir / "master_dataset.parquet"
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # 1. If exists, read and return
    if master_file.exists():
        logger.info(f"{corr_prefix} Reading existing master dataset from {master_file}")
        return pd.read_parquet(master_file)

    # 2. If not exists, materialize (STREAMING)
    logger.info(
        f"{corr_prefix} Master dataset not found. Materializing lazy... (Stream DB -> Parquet)"
    )
    scenario_dir.mkdir(parents=True, exist_ok=True)

    enrichment_build_repo = TrainingEnrichmentBuildRepository(db)
    feature_vector_repo = FeatureVectorRepository(db)
    raw_repo_repo = RawRepositoryRepository(db)

    # Pre-cache RawRepos (usually small number) for language lookup
    # Find all repos involved in this scenario
    # Optimization: Only fetch IDs first? No, we can just fetch all unique repo IDs from enrichment.
    # But for streaming, we might not want to scan all first.
    # Let's just fetch ALL raw repos (it's usually < 1000).
    all_raw_repos = {str(r.id): r for r in raw_repo_repo.find_all()}

    # Stream Processing Configuration
    BATCH_SIZE = 1000
    cursor = enrichment_build_repo.collection.find(
        {
            "scenario_id": enrichment_build_repo.ensure_object_id(scenario_id),
            "extraction_status": ExtractionStatus.COMPLETED.value,
        }
    )

    writer_container = {"writer": None}
    processed_count = 0

    try:
        # Iterate cursor
        # Note: We manually batch from cursor to efficient bulk fetch FeatureVectors
        current_batch = []

        for doc in cursor:
            # Convert PyMongo doc to Entity/Dict locally or just use doc directly
            # Direct doc usage is faster for materialization
            current_batch.append(doc)

            if len(current_batch) >= BATCH_SIZE:
                _process_and_write_batch(
                    current_batch,
                    feature_vector_repo,
                    all_raw_repos,
                    master_file,
                    writer_container=writer_container,
                )
                processed_count += len(current_batch)
                current_batch = []
                logger.info(f"{corr_prefix} Materialized {processed_count} rows...")

        # Process remaining
        if current_batch:
            _process_and_write_batch(
                current_batch,
                feature_vector_repo,
                all_raw_repos,
                master_file,
                writer_container=writer_container,
            )
            processed_count += len(current_batch)

    except Exception as e:
        logger.error(f"{corr_prefix} Materialization failed: {e}")
        # Clean up partial file
        writer = writer_container.get("writer")
        if writer:
            writer.close()
        if master_file.exists():
            master_file.unlink()
        raise e
    finally:
        writer = writer_container.get("writer")
        if writer:
            writer.close()

    logger.info(
        f"{corr_prefix} Materialization complete. Saved {processed_count} rows to {master_file}"
    )

    # Return loaded dataframe
    # If file was explicitly created but empty (no builds), return empty DF
    if not master_file.exists():
        return pd.DataFrame()

    return pd.read_parquet(master_file)


def _process_and_write_batch(
    batch_docs: List[Dict],
    fv_repo: FeatureVectorRepository,
    raw_repos: Dict[str, Any],
    file_path: Any,
    writer_container: Dict[str, Any],
):
    """
    Process a batch of enrichment docs, fetch features, and write to Parquet.
    Updates writer in writer_container if initialized.
    """
    if not batch_docs:
        return

    # Bulk fetch FeatureVectors
    fv_ids = [
        doc.get("feature_vector_id")
        for doc in batch_docs
        if doc.get("feature_vector_id")
    ]
    fvs = fv_repo.find_by_ids(map(str, fv_ids))
    fv_map = {str(fv.id): fv for fv in fvs}

    data = []

    for doc in batch_docs:
        raw_repo_id = str(doc.get("raw_repo_id"))
        raw_repo = raw_repos.get(raw_repo_id)
        primary_language = (
            raw_repo.main_lang if raw_repo and raw_repo.main_lang else "other"
        )

        row_data = {
            "id": str(doc.get("_id")),
            "outcome": doc.get("outcome", 0),
            "repo_full_name": doc.get("repo_full_name", ""),
            "primary_language": primary_language.lower(),
            "build_started_at": doc.get("build_started_at"),
        }

        # Merge features
        fv_id = doc.get("feature_vector_id")
        if fv_id:
            fv = fv_map.get(str(fv_id))
            if fv:
                if fv.features:
                    row_data.update(fv.features)
                if fv.scan_metrics:
                    row_data.update(fv.scan_metrics)

        data.append(row_data)

    if not data:
        return

    df = pd.DataFrame(data)
    table = pa.Table.from_pandas(df)

    # Initialize writer if first batch
    writer = writer_container.get("writer")
    if writer is None:
        writer = pq.ParquetWriter(file_path, table.schema)
        writer_container["writer"] = writer

    # Write batch
    # Note: ParquetWriter enforces schema consistency.
    # Validates that subsequent batches match the schema of the first batch.

    writer.write_table(table)

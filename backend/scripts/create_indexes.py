#!/usr/bin/env python3
"""
MongoDB Index Creation Script for Build Risk Dashboard.

Creates indexes for both Build Risk Evaluation and Dataset Enrichment pipelines.
This script is idempotent - can be run multiple times safely.

Usage:
    cd /home/enrich/build-risk-dashboard/backend
    uv run python scripts/create_indexes.py
"""

import logging
import sys
from typing import List, Tuple

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import OperationFailure

# Add app to path for imports
sys.path.insert(0, "/home/enrich/build-risk-dashboard/backend")

from app.database.mongo import get_database  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_indexes_for_collection(
    db: Database,
    collection_name: str,
    indexes: List[IndexModel],
) -> Tuple[int, int]:
    """
    Create indexes for a collection.

    Returns:
        Tuple of (created_count, skipped_count)
    """
    collection = db[collection_name]
    created = 0
    skipped = 0

    for index in indexes:
        try:
            collection.create_indexes([index])
            logger.info(f"  ✓ Created: {index.document.get('name', 'unnamed')}")
            created += 1
        except OperationFailure as e:
            if "already exists" in str(e) or "duplicate key" in str(e):
                logger.info(
                    f"  ⊘ Already exists: {index.document.get('name', 'unnamed')}"
                )
                skipped += 1
            else:
                logger.error(
                    f"  ✗ Failed: {index.document.get('name', 'unnamed')} - {e}"
                )

    return created, skipped


def create_all_indexes(db: Database) -> None:
    """Create all indexes for both pipelines."""

    total_created = 0
    total_skipped = 0

    # =========================================================================
    # SHARED COLLECTIONS (Used by both pipelines)
    # =========================================================================

    logger.info("\n=== raw_repositories ===")
    created, skipped = create_indexes_for_collection(
        db,
        "raw_repositories",
        [
            IndexModel(
                [("full_name", ASCENDING)],
                unique=True,
                name="unique_full_name",
            ),
            IndexModel(
                [("github_repo_id", ASCENDING)],
                name="github_repo_id",
                sparse=True,
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== raw_build_runs ===")
    created, skipped = create_indexes_for_collection(
        db,
        "raw_build_runs",
        [
            IndexModel(
                [
                    ("raw_repo_id", ASCENDING),
                    ("build_id", ASCENDING),
                    ("provider", ASCENDING),
                ],
                unique=True,
                name="business_key",
            ),
            IndexModel(
                [("raw_repo_id", ASCENDING), ("created_at", DESCENDING)],
                name="repo_created",
            ),
            IndexModel(
                [("raw_repo_id", ASCENDING), ("commit_sha", ASCENDING)],
                name="repo_commit",
            ),
            IndexModel(
                [("raw_repo_id", ASCENDING), ("ci_run_id", ASCENDING)],
                name="ci_run_lookup",
            ),
            IndexModel(
                [("raw_repo_id", ASCENDING), ("effective_sha", ASCENDING)],
                name="repo_effective_sha",
                sparse=True,
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    # =========================================================================
    # BUILD RISK EVALUATION PIPELINE (Model Flow)
    # =========================================================================

    logger.info("\n=== model_repo_configs ===")
    created, skipped = create_indexes_for_collection(
        db,
        "model_repo_configs",
        [
            IndexModel(
                [("full_name", ASCENDING)],
                unique=True,
                name="unique_full_name",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("status", ASCENDING)],
                name="user_status",
            ),
            IndexModel(
                [("raw_repo_id", ASCENDING)],
                name="raw_repo_id",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== model_import_builds ===")
    created, skipped = create_indexes_for_collection(
        db,
        "model_import_builds",
        [
            IndexModel(
                [
                    ("model_repo_config_id", ASCENDING),
                    ("raw_build_run_id", ASCENDING),
                ],
                unique=True,
                name="business_key",
            ),
            IndexModel(
                [("model_repo_config_id", ASCENDING), ("status", ASCENDING)],
                name="config_status",
            ),
            IndexModel(
                [("model_repo_config_id", ASCENDING), ("_id", ASCENDING)],
                name="config_id_order",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== model_training_builds ===")
    created, skipped = create_indexes_for_collection(
        db,
        "model_training_builds",
        [
            IndexModel(
                [("raw_repo_id", ASCENDING), ("raw_build_run_id", ASCENDING)],
                unique=True,
                name="business_key",
            ),
            IndexModel(
                [("model_repo_config_id", ASCENDING), ("extraction_status", ASCENDING)],
                name="config_extraction",
            ),
            IndexModel(
                [("model_repo_config_id", ASCENDING), ("predicted_label", ASCENDING)],
                name="config_prediction",
            ),
            IndexModel(
                [("model_repo_config_id", ASCENDING), ("build_created_at", ASCENDING)],
                name="config_build_created",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    # =========================================================================
    # DATASET ENRICHMENT PIPELINE (Training Scenario Flow)
    # =========================================================================

    logger.info("\n=== build_sources ===")
    created, skipped = create_indexes_for_collection(
        db,
        "build_sources",
        [
            IndexModel(
                [("validation_status", ASCENDING)],
                name="validation_status",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== source_builds ===")
    created, skipped = create_indexes_for_collection(
        db,
        "source_builds",
        [
            IndexModel(
                [("source_id", ASCENDING), ("status", ASCENDING)],
                name="source_status",
            ),
            IndexModel(
                [("source_id", ASCENDING), ("raw_run_id", ASCENDING)],
                name="source_raw_run",
                sparse=True,
            ),
            IndexModel(
                [("source_id", ASCENDING), ("build_id_from_source", ASCENDING)],
                name="source_build_id",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== source_repo_stats ===")
    created, skipped = create_indexes_for_collection(
        db,
        "source_repo_stats",
        [
            IndexModel(
                [("source_id", ASCENDING), ("raw_repo_id", ASCENDING)],
                unique=True,
                name="source_repo",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== training_scenarios ===")
    created, skipped = create_indexes_for_collection(
        db,
        "training_scenarios",
        [
            IndexModel(
                [("status", ASCENDING)],
                name="status",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== training_ingestion_builds ===")
    created, skipped = create_indexes_for_collection(
        db,
        "training_ingestion_builds",
        [
            IndexModel(
                [("scenario_id", ASCENDING), ("status", ASCENDING)],
                name="scenario_status",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("commit_sha", ASCENDING)],
                name="scenario_commit",
            ),
            IndexModel(
                [
                    ("scenario_id", ASCENDING),
                    ("raw_repo_id", ASCENDING),
                    ("commit_sha", ASCENDING),
                ],
                name="scenario_repo_commit",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("ci_run_id", ASCENDING)],
                name="scenario_ci_run",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== training_enrichment_builds ===")
    created, skipped = create_indexes_for_collection(
        db,
        "training_enrichment_builds",
        [
            IndexModel(
                [("scenario_id", ASCENDING), ("extraction_status", ASCENDING)],
                name="scenario_extraction",
            ),
            IndexModel(
                [("ingestion_build_id", ASCENDING)],
                unique=True,
                name="ingestion_build",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("commit_sha", ASCENDING)],
                name="scenario_commit",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== training_dataset_exports ===")
    created, skipped = create_indexes_for_collection(
        db,
        "training_dataset_exports",
        [
            IndexModel(
                [("scenario_id", ASCENDING)],
                name="scenario_id",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== training_dataset_splits ===")
    created, skipped = create_indexes_for_collection(
        db,
        "training_dataset_splits",
        [
            IndexModel(
                [("export_id", ASCENDING)],
                name="export_id",
            ),
            IndexModel(
                [("scenario_id", ASCENDING)],
                name="scenario_id",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== sonar_commit_scans ===")
    created, skipped = create_indexes_for_collection(
        db,
        "sonar_commit_scans",
        [
            IndexModel(
                [("component_key", ASCENDING)],
                unique=True,
                name="component_key",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("status", ASCENDING)],
                name="scenario_status",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("commit_sha", ASCENDING)],
                unique=True,
                name="scenario_commit",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    logger.info("\n=== trivy_commit_scans ===")
    created, skipped = create_indexes_for_collection(
        db,
        "trivy_commit_scans",
        [
            IndexModel(
                [("scenario_id", ASCENDING), ("status", ASCENDING)],
                name="scenario_status",
            ),
            IndexModel(
                [("scenario_id", ASCENDING), ("commit_sha", ASCENDING)],
                unique=True,
                name="scenario_commit",
            ),
        ],
    )
    total_created += created
    total_skipped += skipped

    # =========================================================================
    # SUMMARY
    # =========================================================================

    logger.info("\n" + "=" * 50)
    logger.info(
        f"SUMMARY: Created {total_created} indexes, Skipped {total_skipped} (already exist)"
    )
    logger.info("=" * 50)


def main():
    """Main entry point."""
    logger.info("Starting MongoDB index creation...")
    logger.info("Connecting to database...")

    db = get_database()
    logger.info(f"Connected to database: {db.name}")

    create_all_indexes(db)

    logger.info("\nDone!")


if __name__ == "__main__":
    main()

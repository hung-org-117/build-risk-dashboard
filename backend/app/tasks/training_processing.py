"""
Training Pipeline - Processing Tasks (Phase 2) - Public API.

Tasks have been split into app.tasks.training.processing/ for maintainability:
- common.py: Shared utilities
- orchestrator.py: Entry point tasks
- enrichment.py: Feature extraction dispatch
- finalize.py: Finalize and error handlers
- scans.py: Scan dispatch tasks
- retry.py: Retry tasks

All tasks preserve their original Celery task names via `name=` parameter.
"""

# Re-export all tasks from submodules
from app.tasks.training.processing import (
    dispatch_enrichment_batches,
    dispatch_scans_and_processing,
    dispatch_scenario_scans,
    finalize_feature_extraction,
    finalize_scan_dispatch,
    handle_processing_chain_error,
    process_retry_scan_batch,
    process_scan_batch,
    process_single_enrichment,
    reprocess_failed_feature_extraction,
    retry_failed_scenario_scans,
    start_scenario_processing,
)
from app.tasks.training.processing.common import (
    create_scenario_failure_handler,
    create_training_enrichment_build_failure_handler,
)

__all__ = [
    # Orchestrator
    "start_scenario_processing",
    # Enrichment
    "dispatch_scans_and_processing",
    "dispatch_enrichment_batches",
    "process_single_enrichment",
    # Finalize
    "finalize_feature_extraction",
    "handle_processing_chain_error",
    # Scans
    "dispatch_scenario_scans",
    "process_scan_batch",
    "finalize_scan_dispatch",
    # Retry
    "reprocess_failed_feature_extraction",
    "retry_failed_scenario_scans",
    "process_retry_scan_batch",
    # Helpers
    "create_scenario_failure_handler",
    "create_training_enrichment_build_failure_handler",
]

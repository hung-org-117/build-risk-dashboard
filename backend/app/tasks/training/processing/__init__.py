"""
Training Processing Tasks Package.

Provides public API for all training processing tasks:
- start_scenario_processing (orchestrator)
- dispatch_scans_and_processing (enrichment)
- dispatch_enrichment_batches (enrichment)
- process_single_enrichment (enrichment)
- finalize_feature_extraction (finalize)
- handle_processing_chain_error (finalize)
- dispatch_scenario_scans (scans)
- process_scan_batch (scans)
- finalize_scan_dispatch (scans)
- reprocess_failed_feature_extraction (retry)
- retry_failed_scenario_scans (retry)
- process_retry_scan_batch (retry)
"""

from app.tasks.training.processing.base import ScenarioProcessingTask
from app.tasks.training.processing.enrichment import (
    dispatch_enrichment_batches,
    dispatch_scans_and_processing,
    process_single_enrichment,
)
from app.tasks.training.processing.finalize import (
    finalize_feature_extraction,
    handle_processing_chain_error,
)
from app.tasks.training.processing.orchestrator import start_scenario_processing
from app.tasks.training.processing.retry import (
    process_retry_scan_batch,
    reprocess_failed_feature_extraction,
    retry_failed_scenario_scans,
)
from app.tasks.training.processing.scans import (
    dispatch_scenario_scans,
    finalize_scan_dispatch,
    process_scan_batch,
)

__all__ = [
    # Base Classes
    "ScenarioProcessingTask",
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
]

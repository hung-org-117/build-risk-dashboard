"""
SSE Event Publishing Utilities for Real-time Updates.

This module provides functions to publish events to Redis pub/sub,
which are then forwarded to SSE clients by the API layer.

=== EVENT NAMING CONVENTION ===

Format: {PIPELINE}.{ENTITY}.{ACTION}

PIPELINES:
- MODEL: Model Training Pipeline (repositories, predictions)
- SCENARIO: Training Scenario Pipeline (datasets, features)
- SYSTEM: System-wide events (notifications, alerts)

ENTITIES:
- REPO: Repository-level updates
- BUILD: Individual build updates
- INGESTION: Resource ingestion (git, logs)
- PROCESSING: Feature extraction
- SCAN: Security scans (Trivy, SonarQube)
- NOTIFICATION: User notifications

ACTIONS:
- UPDATED: Status/data change
- PROGRESS: Progress update (chunked operations)
- ERROR: Error occurred

=== EVENT CATALOG ===

MODEL Pipeline:
- MODEL.REPO.UPDATED        : Repository status change
- MODEL.BUILD.UPDATED       : Build status change
- MODEL.INGESTION.PROGRESS  : Ingestion resource progress
- MODEL.INGESTION.ERROR     : Ingestion error
- MODEL.PROCESSING.UPDATED  : Feature extraction progress
- MODEL.PREDICTION.UPDATED  : Prediction progress

SCENARIO Pipeline:
- SCENARIO.UPDATED          : Scenario aggregate status
- SCENARIO.INGESTION.UPDATED: Ingestion build status
- SCENARIO.PROCESSING.UPDATED: Processing/enrichment build status
- SCENARIO.SCAN.UPDATED     : Scan status change
- SCENARIO.SCAN.ERROR       : Scan error

SYSTEM:
- SYSTEM.NOTIFICATION       : User notification
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Redis channel for SSE events
EVENTS_CHANNEL = "events"


# =============================================================================
# Event Type Constants
# =============================================================================


class EventType:
    """SSE Event type constants."""

    # Model Pipeline Events
    MODEL_REPO_UPDATED = "MODEL.REPO.UPDATED"
    MODEL_BUILD_UPDATED = "MODEL.BUILD.UPDATED"
    MODEL_INGESTION_PROGRESS = "MODEL.INGESTION.PROGRESS"
    MODEL_INGESTION_ERROR = "MODEL.INGESTION.ERROR"
    MODEL_PROCESSING_UPDATED = "MODEL.PROCESSING.UPDATED"
    MODEL_PREDICTION_UPDATED = "MODEL.PREDICTION.UPDATED"

    # Scenario Pipeline Events
    SCENARIO_UPDATED = "SCENARIO.UPDATED"
    SCENARIO_INGESTION_UPDATED = "SCENARIO.INGESTION.UPDATED"
    SCENARIO_PROCESSING_UPDATED = "SCENARIO.PROCESSING.UPDATED"
    SCENARIO_SCAN_UPDATED = "SCENARIO.SCAN.UPDATED"
    SCENARIO_SCAN_ERROR = "SCENARIO.SCAN.ERROR"

    # System Events
    SYSTEM_NOTIFICATION = "SYSTEM.NOTIFICATION"


# =============================================================================
# Core Publishing Function
# =============================================================================


def _get_redis_client():
    """Get a synchronous Redis client."""
    return redis.from_url(settings.REDIS_URL)


def publish_event(event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Publish an event to the Redis events channel.

    Args:
        event_type: Event type (use EventType constants)
        payload: Event payload data

    Returns:
        True if published successfully, False otherwise
    """
    try:
        redis_client = _get_redis_client()
        message = json.dumps({"type": event_type, "payload": payload})
        result = redis_client.publish(EVENTS_CHANNEL, message)
        logger.info(f"Published {event_type} to {result} subscribers")
        logger.debug(f"Event payload: {payload}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish event {event_type}: {e}")
        return False


# =============================================================================
# MODEL PIPELINE EVENTS
# =============================================================================


def publish_model_repo_updated(
    repo_id: str,
    status: str,
    message: str = "",
    stats: Optional[Dict[str, int]] = None,
) -> bool:
    """
    Publish MODEL.REPO.UPDATED event for repository status changes.

    Used when ModelRepoConfig status changes (QUEUED -> FETCHING -> INGESTING -> etc.)

    Args:
        repo_id: ModelRepoConfig ID
        status: New status value
        message: Optional status message
        stats: Optional stats dict (builds_fetched, builds_ingested, etc.)

    Returns:
        True if published successfully
    """
    payload = {
        "repo_id": repo_id,
        "status": status,
        "message": message,
    }
    if stats:
        payload["stats"] = stats

    return publish_event(EventType.MODEL_REPO_UPDATED, payload)


def publish_model_build_updated(
    repo_id: str,
    build_id: str,
    status: str,
    extraction_status: Optional[str] = None,
    prediction_status: Optional[str] = None,
    predicted_label: Optional[str] = None,
) -> bool:
    """
    Publish MODEL.BUILD.UPDATED event for build status changes.

    Used for ModelImportBuild or ModelTrainingBuild status updates.

    Args:
        repo_id: ModelRepoConfig ID
        build_id: Build ID (ModelImportBuild or ModelTrainingBuild)
        status: Build status
        extraction_status: Feature extraction status (optional)
        prediction_status: Prediction status (optional)
        predicted_label: Prediction result label (optional)

    Returns:
        True if published successfully
    """
    payload = {
        "repo_id": repo_id,
        "build_id": build_id,
        "status": status,
    }
    if extraction_status:
        payload["extraction_status"] = extraction_status
    if prediction_status:
        payload["prediction_status"] = prediction_status
    if predicted_label:
        payload["predicted_label"] = predicted_label

    return publish_event(EventType.MODEL_BUILD_UPDATED, payload)


def publish_ingestion_progress(
    repo_id: str,
    resource: str,
    status: str,
    pipeline_type: str = "model",
    builds_affected: int = 0,
    chunk_index: int = 0,
    total_chunks: int = 1,
    completed_commit_shas: Optional[List[str]] = None,
    failed_commit_shas: Optional[List[str]] = None,
    completed_build_ids: Optional[List[str]] = None,
    failed_build_ids: Optional[List[str]] = None,
) -> bool:
    """
    Publish ingestion progress event for both Model and Scenario pipelines.

    Used during git clone, worktree creation, and log downloads.

    Args:
        repo_id: ModelRepoConfig ID (model) or TrainingScenario ID (dataset)
        resource: Resource type (git_history, git_worktree, build_logs)
        status: Status (in_progress, completed, failed, completed_with_errors)
        pipeline_type: Pipeline type ("model" or "dataset")
        builds_affected: Number of builds affected
        chunk_index: Current chunk index
        total_chunks: Total chunks
        completed_commit_shas: Successfully processed commits
        failed_commit_shas: Failed commits
        completed_build_ids: Successfully processed builds
        failed_build_ids: Failed builds

    Returns:
        True if published successfully
    """
    # Determine event type based on pipeline
    if pipeline_type == "dataset":
        event_type = EventType.SCENARIO_INGESTION_UPDATED
        payload = {
            "scenario_id": repo_id,
            "resource": resource,
            "status": status,
        }
    else:
        event_type = EventType.MODEL_INGESTION_PROGRESS
        payload = {
            "repo_id": repo_id,
            "resource": resource,
            "status": status,
        }

    # Add common fields
    payload.update(
        {
            "builds_affected": builds_affected,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
        }
    )

    if completed_commit_shas:
        payload["completed_commit_shas"] = completed_commit_shas
    if failed_commit_shas:
        payload["failed_commit_shas"] = failed_commit_shas
    if completed_build_ids:
        payload["completed_build_ids"] = completed_build_ids
    if failed_build_ids:
        payload["failed_build_ids"] = failed_build_ids

    return publish_event(event_type, payload)


def publish_model_ingestion_error(
    repo_id: str,
    resource: str,
    error: str,
    chunk_index: int = 0,
    correlation_id: Optional[str] = None,
) -> bool:
    """
    Publish MODEL.INGESTION.ERROR event for ingestion failures.

    Args:
        repo_id: ModelRepoConfig ID or RawRepository ID
        resource: Resource type that failed
        error: Error message
        chunk_index: Chunk that failed (if applicable)
        correlation_id: Correlation ID for tracing

    Returns:
        True if published successfully
    """
    payload = {
        "repo_id": repo_id,
        "resource": resource,
        "error": error,
        "chunk_index": chunk_index,
    }
    if correlation_id:
        payload["correlation_id"] = correlation_id

    return publish_event(EventType.MODEL_INGESTION_ERROR, payload)


def publish_model_processing_updated(
    repo_id: str,
    build_id: str,
    extraction_status: str,
    feature_count: int = 0,
    expected_feature_count: int = 0,
    error: Optional[str] = None,
    ci_run_id: Optional[str] = None,
    commit_sha: Optional[str] = None,
) -> bool:
    """
    Publish MODEL.PROCESSING.UPDATED event for feature extraction progress.

    Used when ModelTrainingBuild extraction status changes during feature extraction.

    Args:
        repo_id: ModelRepoConfig ID
        build_id: ModelTrainingBuild ID
        extraction_status: Extraction status (pending, in_progress, completed, partial, failed)
        feature_count: Number of features extracted
        expected_feature_count: Expected number of features
        error: Error message (if failed)
        ci_run_id: CI run identifier
        commit_sha: Git commit SHA

    Returns:
        True if published successfully
    """
    payload = {
        "repo_id": repo_id,
        "build_id": build_id,
        "extraction_status": extraction_status,
        "feature_count": feature_count,
        "expected_feature_count": expected_feature_count,
    }
    if error:
        payload["error"] = error
    if ci_run_id:
        payload["ci_run_id"] = ci_run_id
    if commit_sha:
        payload["commit_sha"] = commit_sha

    return publish_event(EventType.MODEL_PROCESSING_UPDATED, payload)


def publish_model_prediction_updated(
    repo_id: str,
    build_id: str,
    prediction_status: str,
    predicted_label: Optional[str] = None,
    prediction_confidence: Optional[float] = None,
    error: Optional[str] = None,
    ci_run_id: Optional[str] = None,
    commit_sha: Optional[str] = None,
) -> bool:
    """
    Publish MODEL.PREDICTION.UPDATED event for prediction progress.

    Used when ModelTrainingBuild prediction status changes during ML inference.

    Args:
        repo_id: ModelRepoConfig ID
        build_id: ModelTrainingBuild ID
        prediction_status: Prediction status (pending, in_progress, completed, failed)
        predicted_label: Risk level prediction (LOW, MEDIUM, HIGH)
        prediction_confidence: Confidence score (0.0-1.0)
        error: Error message (if failed)
        ci_run_id: CI run identifier
        commit_sha: Git commit SHA

    Returns:
        True if published successfully
    """
    payload = {
        "repo_id": repo_id,
        "build_id": build_id,
        "prediction_status": prediction_status,
    }
    if predicted_label:
        payload["predicted_label"] = predicted_label
    if prediction_confidence is not None:
        payload["prediction_confidence"] = prediction_confidence
    if error:
        payload["error"] = error
    if ci_run_id:
        payload["ci_run_id"] = ci_run_id
    if commit_sha:
        payload["commit_sha"] = commit_sha

    return publish_event(EventType.MODEL_PREDICTION_UPDATED, payload)


# =============================================================================
# SCENARIO PIPELINE EVENTS
# =============================================================================


def publish_scenario_updated(
    scenario,
    error: Optional[str] = None,
) -> bool:
    """
    Publish SCENARIO.UPDATED event with full scenario state.

    Used when TrainingScenario status or aggregate stats change.

    Args:
        scenario: TrainingScenario entity instance
        error: Optional error message

    Returns:
        True if published successfully
    """
    # Extract values from entity
    scenario_id = str(scenario.id)
    status = scenario.status.value if hasattr(scenario.status, "value") else scenario.status
    builds_total = getattr(scenario, "builds_total", 0) or 0
    builds_ingested = getattr(scenario, "builds_ingested", 0) or 0
    builds_features_extracted = getattr(scenario, "builds_features_extracted", 0) or 0
    builds_ingestion_failed = getattr(scenario, "builds_ingestion_failed", 0) or 0
    builds_features_extracted_failed = getattr(scenario, "builds_features_extracted_failed", 0) or 0
    builds_missing_resource = getattr(scenario, "builds_missing_resource", 0) or 0
    scans_total = getattr(scenario, "scans_total", 0) or 0
    scans_completed = getattr(scenario, "scans_completed", 0) or 0
    scans_failed = getattr(scenario, "scans_failed", 0) or 0
    feature_extraction_completed = getattr(scenario, "feature_extraction_completed", False)
    scan_extraction_completed = getattr(scenario, "scan_extraction_completed", False)

    # Calculate progress percentages
    ingestion_progress = round((builds_ingested / builds_total) * 100, 1) if builds_total > 0 else 0
    feature_extraction_progress = (
        round((builds_features_extracted / builds_total) * 100, 1) if builds_total > 0 else 0
    )
    scan_progress = round((scans_completed / scans_total) * 100, 1) if scans_total > 0 else 0

    payload = {
        "scenario_id": scenario_id,
        "status": status,
        "builds_total": builds_total,
        "builds_ingested": builds_ingested,
        "builds_features_extracted": builds_features_extracted,
        "builds_ingestion_failed": builds_ingestion_failed,
        "builds_features_extracted_failed": builds_features_extracted_failed,
        "builds_missing_resource": builds_missing_resource,
        "ingestion_progress": ingestion_progress,
        "feature_extraction_progress": feature_extraction_progress,
        "scan_progress": scan_progress,
        "scans_total": scans_total,
        "scans_completed": scans_completed,
        "scans_failed": scans_failed,
        "feature_extraction_completed": feature_extraction_completed,
        "scan_extraction_completed": scan_extraction_completed,
    }
    if error:
        payload["error"] = error

    return publish_event(EventType.SCENARIO_UPDATED, payload)


def publish_scenario_ingestion_updated(
    scenario_id: str,
    build_id: str,
    status: str,
    resource_status: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    ci_run_id: Optional[str] = None,
    commit_sha: Optional[str] = None,
    repo_full_name: Optional[str] = None,
) -> bool:
    """
    Publish SCENARIO.INGESTION.UPDATED event for ingestion build status.

    Used when TrainingIngestionBuild status changes.

    Args:
        scenario_id: TrainingScenario ID
        build_id: TrainingIngestionBuild ID
        status: Build status (pending, ingesting, ingested, missing_resource, failed)
        resource_status: Per-resource status dict
        error: Error message
        ci_run_id: CI run identifier
        commit_sha: Git commit SHA
        repo_full_name: Repository full name

    Returns:
        True if published successfully
    """
    payload = {
        "scenario_id": scenario_id,
        "build_id": build_id,
        "status": status,
    }
    if resource_status:
        payload["resource_status"] = resource_status
    if error:
        payload["error"] = error
    if ci_run_id:
        payload["ci_run_id"] = ci_run_id
    if commit_sha:
        payload["commit_sha"] = commit_sha
    if repo_full_name:
        payload["repo_full_name"] = repo_full_name

    return publish_event(EventType.SCENARIO_INGESTION_UPDATED, payload)


def publish_scenario_processing_updated(
    scenario_id: str,
    build_id: str,
    extraction_status: str,
    feature_count: int = 0,
    expected_feature_count: int = 0,
    error: Optional[str] = None,
    ci_run_id: Optional[str] = None,
    commit_sha: Optional[str] = None,
    repo_full_name: Optional[str] = None,
    enriched_at: Optional[str] = None,
) -> bool:
    """
    Publish SCENARIO.PROCESSING.UPDATED event for processing build status.

    Used when TrainingEnrichmentBuild extraction status changes.

    Args:
        scenario_id: TrainingScenario ID
        build_id: TrainingEnrichmentBuild ID
        extraction_status: Extraction status (pending, in_progress, completed, partial, failed)
        feature_count: Number of features extracted
        expected_feature_count: Expected features
        error: Error message
        ci_run_id: CI run identifier
        commit_sha: Git commit SHA
        repo_full_name: Repository full name
        enriched_at: ISO timestamp

    Returns:
        True if published successfully
    """
    payload = {
        "scenario_id": scenario_id,
        "build_id": build_id,
        "extraction_status": extraction_status,
        "feature_count": feature_count,
        "expected_feature_count": expected_feature_count,
    }
    if error:
        payload["error"] = error
    if ci_run_id:
        payload["ci_run_id"] = ci_run_id
    if commit_sha:
        payload["commit_sha"] = commit_sha
    if repo_full_name:
        payload["repo_full_name"] = repo_full_name
    if enriched_at:
        payload["enriched_at"] = enriched_at

    return publish_event(EventType.SCENARIO_PROCESSING_UPDATED, payload)


def publish_scenario_scan_updated(
    scenario_id: str,
    scan_id: str,
    commit_sha: str,
    tool_type: str,
    status: str,
    error: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
    builds_affected: int = 0,
) -> bool:
    """
    Publish SCENARIO.SCAN.UPDATED event for scan status changes.

    Used when TrivyCommitScan or SonarCommitScan status changes.

    Args:
        scenario_id: TrainingScenario ID
        scan_id: Scan record ID
        commit_sha: Commit being scanned
        tool_type: "trivy" or "sonarqube"
        status: Scan status (pending, scanning, completed, failed)
        error: Error message (if failed)
        metrics: Scan metrics (if completed)
        builds_affected: Builds updated with results

    Returns:
        True if published successfully
    """
    payload = {
        "scenario_id": scenario_id,
        "scan_id": scan_id,
        "commit_sha": commit_sha,
        "tool_type": tool_type,
        "status": status,
        "builds_affected": builds_affected,
    }
    if error:
        payload["error"] = error
    if metrics:
        payload["metrics"] = metrics

    return publish_event(EventType.SCENARIO_SCAN_UPDATED, payload)


def publish_scenario_scan_error(
    scenario_id: str,
    scan_id: str,
    commit_sha: str,
    tool_type: str,
    error: str,
    retry_count: int = 0,
) -> bool:
    """
    Publish SCENARIO.SCAN.ERROR event for scan failures.

    Args:
        scenario_id: TrainingScenario ID
        scan_id: Scan record ID
        commit_sha: Commit that failed
        tool_type: "trivy" or "sonarqube"
        error: Error message
        retry_count: Number of retries

    Returns:
        True if published successfully
    """
    payload = {
        "scenario_id": scenario_id,
        "scan_id": scan_id,
        "commit_sha": commit_sha,
        "tool_type": tool_type,
        "error": error,
        "retry_count": retry_count,
    }
    return publish_event(EventType.SCENARIO_SCAN_ERROR, payload)


# =============================================================================
# SYSTEM EVENTS
# =============================================================================


def publish_system_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Publish SYSTEM.NOTIFICATION event for user notifications.

    Args:
        user_id: Target user ID
        title: Notification title
        message: Notification message
        notification_type: Type (info, success, warning, error)
        data: Additional data

    Returns:
        True if published successfully
    """
    payload = {
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notification_type,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if data:
        payload["data"] = data

    return publish_event(EventType.SYSTEM_NOTIFICATION, payload)

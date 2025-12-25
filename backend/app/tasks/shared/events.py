"""
Shared event publishing utilities for real-time WebSocket updates.

This module provides functions to publish events to Redis pub/sub,
which are then forwarded to WebSocket clients by the API layer.
"""

import json
import logging
from typing import Any, Dict, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Redis channel for WebSocket events
EVENTS_CHANNEL = "events"


def _get_redis_client():
    """Get a synchronous Redis client."""
    return redis.from_url(settings.REDIS_URL)


def publish_event(event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Publish an event to the Redis events channel.

    Args:
        event_type: Event type (e.g., "REPO_UPDATE", "BUILD_UPDATE")
        payload: Event payload data

    Returns:
        True if published successfully, False otherwise
    """
    try:
        redis_client = _get_redis_client()
        message = json.dumps({"type": event_type, "payload": payload})
        redis_client.publish(EVENTS_CHANNEL, message)
        return True
    except Exception as e:
        logger.error(f"Failed to publish event {event_type}: {e}")
        return False


def publish_repo_status(
    repo_id: str,
    status: str,
    message: str = "",
    stats: Optional[Dict[str, int]] = None,
) -> bool:
    """
    Publish repository status update for real-time UI updates.

    Args:
        repo_id: Repository ID (ModelRepoConfig._id or raw_repo_id)
        status: Status value (queued, importing, processing, imported, failed)
        message: Optional status message
        stats: Optional stats to include (total_builds_imported, etc.)

    Returns:
        True if published successfully, False otherwise
    """
    payload = {
        "repo_id": repo_id,
        "status": status,
        "message": message,
    }
    if stats:
        payload["stats"] = stats

    return publish_event("REPO_UPDATE", payload)


def publish_build_status(repo_id: str, build_id: str, status: str) -> bool:
    """
    Publish build status update for real-time UI updates.

    Args:
        repo_id: Repository ID
        build_id: Build ID
        status: Build status (pending, in_progress, completed, failed)

    Returns:
        True if published successfully, False otherwise
    """
    payload = {
        "repo_id": repo_id,
        "build_id": build_id,
        "status": status,
    }
    return publish_event("BUILD_UPDATE", payload)

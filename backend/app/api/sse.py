"""
SSE (Server-Sent Events) API for real-time updates.

This module replaces WebSocket with SSE for one-way server-to-client streaming:
- Global events (repo updates, build updates, notifications)
- Job-specific enrichment progress
- System logs streaming
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pymongo.database import Database

from app.config import settings
from app.database.mongo import get_db
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.services.auth_service import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SSE"])

REDIS_CHANNEL_PREFIX = "enrichment:progress:"


async def get_sse_user(request: Request, db: Database = Depends(get_db)) -> dict:
    """
    Custom auth for SSE that reads cookie directly from Request.
    EventSource doesn't work well with FastAPI's Cookie() dependency.
    """
    # Debug logging
    logger.info(
        f"SSE auth - cookies: {list(request.cookies.keys())}, query: {dict(request.query_params)}"
    )

    # Try to get token from cookie
    token: Optional[str] = request.cookies.get("access_token")

    # Fallback to query param
    if not token:
        token = request.query_params.get("token")

    if not token:
        logger.warning("SSE auth failed - no token in cookie or query param")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Auth error: {str(e)}",
        )


async def get_async_redis():
    """Get async Redis client."""
    return await aioredis.from_url(settings.REDIS_URL)


def format_sse(data: dict, event: str | None = None) -> str:
    """Format data as SSE message."""
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # Empty line to end message
    return "\n".join(lines) + "\n"


async def sse_events_generator(
    user: dict,
    db: Database,
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for the connected user.

    Streams events from Redis 'events' channel with RBAC filtering.
    """
    user_id = str(user["_id"])
    role = user.get("role", "user")

    # Load user permissions (accessible repos)
    repo_config_repo = ModelRepoConfigRepository(db)
    accessible_raw_repo_ids = user.get("github_accessible_repos", [])

    allowed_config_ids = set()
    if accessible_raw_repo_ids:
        configs = repo_config_repo.find_many(
            {"raw_repo_id": {"$in": accessible_raw_repo_ids}}
        )
        allowed_config_ids = {str(c.id) for c in configs}

    logger.info(
        f"SSE connected for user {user_id}. Access to {len(allowed_config_ids)} repos."
    )

    # Send initial connection message
    yield format_sse({"type": "connected", "message": "SSE stream connected"})

    # Create Redis subscription
    redis_client = await get_async_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("events")

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=30.0,  # Send heartbeat every 30s
                )

                if message:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    if data:
                        try:
                            event = json.loads(data)
                            event_type = event.get("type")
                            payload = event.get("payload", {})

                            # === FILTERING LOGIC (same as WebSocket) ===

                            # 1. User Notifications (Direct Message)
                            if event_type == "USER_NOTIFICATION":
                                target_user_id = payload.get("user_id")
                                if target_user_id and target_user_id != user_id:
                                    continue  # Not for this user

                            # 2. Repo/Build Events (RBAC)
                            elif event_type in ("REPO_UPDATE", "BUILD_UPDATE"):
                                repo_id = payload.get("repo_id")
                                if role != "admin":
                                    if not repo_id or repo_id not in allowed_config_ids:
                                        continue

                            # 3. System Events (Admin only)
                            elif event_type == "SYSTEM":
                                if role != "admin":
                                    continue

                            # 4. Scan/Ingestion (RBAC via repo_id)
                            elif event_type in (
                                "SCAN_UPDATE",
                                "INGESTION_BUILD_UPDATE",
                            ):
                                repo_id = payload.get("repo_id")
                                if repo_id and role != "admin":
                                    if repo_id not in allowed_config_ids:
                                        continue

                            # === END FILTERING ===

                            yield format_sse(event, event_type)

                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse event: {data}")

                # No else here - only send heartbeat on timeout, not on every empty message

            except asyncio.TimeoutError:
                # Send heartbeat on timeout (every 30s)
                yield format_sse({"type": "heartbeat"})


    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for user {user_id}")
    except Exception as e:
        logger.error(f"SSE error for user {user_id}: {e}")
    finally:
        await pubsub.unsubscribe("events")
        await redis_client.close()
        logger.info(f"SSE disconnected for user {user_id}")


async def sse_enrichment_generator(
    job_id: str,
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a specific enrichment job.

    Streams progress updates from Redis channel for the job.
    """
    logger.info(f"SSE enrichment stream connected for job {job_id}")

    # Send initial connection message
    yield format_sse(
        {
            "type": "connected",
            "job_id": job_id,
            "message": "Connected to enrichment progress stream",
        }
    )

    redis_client = await get_async_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{REDIS_CHANNEL_PREFIX}{job_id}")

    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=30.0,
                )

                if message:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    if data:
                        event = json.loads(data)
                        yield format_sse(event, event.get("type", "progress"))

                        # Close on completion
                        if event.get("type") in ("complete", "error"):
                            break
                else:
                    yield format_sse({"type": "heartbeat"})

            except asyncio.TimeoutError:
                yield format_sse({"type": "heartbeat"})

    except asyncio.CancelledError:
        logger.info(f"SSE enrichment stream cancelled for job {job_id}")
    except Exception as e:
        logger.error(f"SSE enrichment error for job {job_id}: {e}")
    finally:
        await pubsub.unsubscribe(f"{REDIS_CHANNEL_PREFIX}{job_id}")
        await redis_client.close()
        logger.info(f"SSE enrichment disconnected for job {job_id}")


async def sse_logs_generator(request: Request) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for system logs streaming.

    Streams logs from Redis 'system_logs' channel.
    """
    logger.info("SSE logs stream connected")

    yield format_sse(
        {
            "type": "connected",
            "message": "Connected to system logs stream",
        }
    )

    redis_client = await get_async_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("system_logs")

    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=30.0,
                )

                if message:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    if data:
                        try:
                            log_entry = json.loads(data)
                            yield format_sse(log_entry, "log")
                        except json.JSONDecodeError:
                            yield format_sse({"message": data}, "log")
                else:
                    yield format_sse({"type": "heartbeat"})

            except asyncio.TimeoutError:
                yield format_sse({"type": "heartbeat"})

    except asyncio.CancelledError:
        logger.info("SSE logs stream cancelled")
    except Exception as e:
        logger.error(f"SSE logs error: {e}")
    finally:
        await pubsub.unsubscribe("system_logs")
        await redis_client.close()
        logger.info("SSE logs disconnected")


@router.get("/sse/events")
async def sse_events(
    request: Request,
    user: dict = Depends(get_sse_user),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
):
    """
    SSE endpoint for global events stream.

    Streams real-time updates for:
    - REPO_UPDATE: Repository status changes
    - BUILD_UPDATE: Build processing updates
    - ENRICHMENT_UPDATE: Dataset enrichment progress
    - DATASET_UPDATE: Dataset validation updates
    - USER_NOTIFICATION: User-specific notifications
    - INGESTION_BUILD_UPDATE: Ingestion progress
    - SCAN_UPDATE: Security scan updates

    Events are filtered based on user role and repository access.
    """
    return StreamingResponse(
        sse_events_generator(user, db, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/sse/enrichment/{job_id}")
async def sse_enrichment(
    job_id: str,
    request: Request,
):
    """
    SSE endpoint for enrichment job progress.

    Streams progress updates for a specific enrichment job:
    - connected: Initial connection confirmation
    - progress: Processing progress updates
    - complete: Job completion notification
    - error: Error notification
    - heartbeat: Keep-alive signal

    The stream automatically closes when the job completes or errors.
    """
    return StreamingResponse(
        sse_enrichment_generator(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sse/logs")
async def sse_logs(request: Request):
    """
    SSE endpoint for system logs streaming.

    Streams real-time system logs from Redis.
    Intended for admin monitoring dashboard.
    """
    return StreamingResponse(
        sse_logs_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

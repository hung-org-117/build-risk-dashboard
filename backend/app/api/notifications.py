"""Notification API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pymongo.database import Database
from bson import ObjectId
from typing import Optional

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.repositories.notification import NotificationRepository
from app.entities.notification import Notification, NotificationType


router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================================================
# DTOs
# ============================================================================


class NotificationResponse(BaseModel):
    """Response DTO for a single notification."""

    id: str
    type: str
    title: str
    message: str
    is_read: bool
    link: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: str


class NotificationListResponse(BaseModel):
    """Response DTO for notification list."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Response DTO for unread count."""

    count: int


class MarkReadResponse(BaseModel):
    """Response DTO for mark as read operations."""

    success: bool
    marked_count: int = 1


class CreateNotificationRequest(BaseModel):
    """Request DTO to create a notification (for testing/admin)."""

    type: NotificationType
    title: str
    message: str
    link: Optional[str] = None
    metadata: Optional[dict] = None


# ============================================================================
# Helper Functions
# ============================================================================


def _to_response(notification: Notification) -> NotificationResponse:
    """Convert entity to response DTO."""
    return NotificationResponse(
        id=str(notification.id),
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        is_read=notification.is_read,
        link=notification.link,
        metadata=notification.metadata,
        created_at=notification.created_at.isoformat(),
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List notifications for the current user."""
    repo = NotificationRepository(db)
    user_id = ObjectId(current_user["_id"])

    items, total = repo.find_by_user(
        user_id, skip=skip, limit=limit, unread_only=unread_only
    )
    unread_count = repo.count_unread(user_id)

    return NotificationListResponse(
        items=[_to_response(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the count of unread notifications."""
    repo = NotificationRepository(db)
    user_id = ObjectId(current_user["_id"])
    count = repo.count_unread(user_id)
    return UnreadCountResponse(count=count)


@router.put("/{notification_id}/read", response_model=MarkReadResponse)
def mark_as_read(
    notification_id: str,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a single notification as read."""
    repo = NotificationRepository(db)

    # Verify the notification belongs to the current user
    notification = repo.find_by_id(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    user_id = ObjectId(current_user["_id"])
    if notification.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    success = repo.mark_as_read(ObjectId(notification_id))
    return MarkReadResponse(success=success, marked_count=1 if success else 0)


@router.put("/read-all", response_model=MarkReadResponse)
def mark_all_as_read(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    repo = NotificationRepository(db)
    user_id = ObjectId(current_user["_id"])
    count = repo.mark_all_as_read(user_id)
    return MarkReadResponse(success=True, marked_count=count)


@router.post(
    "/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED
)
def create_notification(
    request: CreateNotificationRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a notification (for testing/admin purposes)."""
    repo = NotificationRepository(db)
    user_id = ObjectId(current_user["_id"])

    notification = Notification(
        user_id=user_id,
        type=request.type,
        title=request.title,
        message=request.message,
        link=request.link,
        metadata=request.metadata,
    )

    created = repo.insert_one(notification)
    return _to_response(created)

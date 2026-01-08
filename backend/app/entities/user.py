from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseEntity


class NotificationSubscription(BaseModel):
    """Per-event notification channel flags."""

    in_app: bool = True
    email: bool = False


def default_user_subscriptions() -> Dict[str, NotificationSubscription]:
    """Default subscriptions for user-facing notification types."""
    return {
        "high_risk_detected": NotificationSubscription(in_app=True, email=True),
        "build_prediction_ready": NotificationSubscription(in_app=True, email=False),
    }


class User(BaseEntity):
    """User entity with settings embedded."""

    email: str
    name: Optional[str] = None
    role: Literal["admin", "user"] = "user"
    notification_email: Optional[str] = None
    github_accessible_repos: List[str] = Field(default_factory=list)
    github_repos_synced_at: Optional[datetime] = None

    # Notification preferences
    browser_notifications: bool = Field(
        default=True, description="Enable browser notifications"
    )
    email_notifications_enabled: bool = Field(
        default=False, description="Enable email notifications for this user"
    )
    subscriptions: Dict[str, NotificationSubscription] = Field(
        default_factory=default_user_subscriptions,
        description="Per-event notification subscriptions",
    )

    class Config:
        collection = "users"
        use_enum_values = True


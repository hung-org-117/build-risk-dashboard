from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.entities.base import PyObjectIdStr


class NotificationSubscriptionDto(BaseModel):
    """Per-event notification channel flags."""

    in_app: bool = True
    email: bool = False


class UserResponse(BaseModel):
    id: PyObjectIdStr = Field(..., alias="_id")
    email: str
    name: Optional[str] = None
    role: Literal["admin", "user"] = "user"
    notification_email: Optional[str] = None
    browser_notifications: bool = True
    email_notifications_enabled: bool = False
    subscriptions: Dict[str, NotificationSubscriptionDto] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    notification_email: Optional[str] = None
    browser_notifications: Optional[bool] = None
    email_notifications_enabled: Optional[bool] = None
    subscriptions: Optional[Dict[str, NotificationSubscriptionDto]] = None


class OAuthIdentityResponse(BaseModel):
    id: PyObjectIdStr = Field(..., alias="_id")
    user_id: PyObjectIdStr
    provider: str
    external_user_id: str
    scopes: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)

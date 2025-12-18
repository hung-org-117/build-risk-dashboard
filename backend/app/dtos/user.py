"""User and authentication DTOs"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


from app.entities.base import PyObjectIdStr


class UserResponse(BaseModel):
    id: PyObjectIdStr = Field(..., alias="_id")
    email: str
    name: Optional[str] = None
    role: Literal["admin", "user"] = "user"
    notification_email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    notification_email: Optional[str] = None


class OAuthIdentityResponse(BaseModel):
    id: PyObjectIdStr = Field(..., alias="_id")
    user_id: PyObjectIdStr
    provider: str
    external_user_id: str
    scopes: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)

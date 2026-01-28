"""DTOs for Admin User Management API."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.entities.base import PyObjectIdStr


class GithubIdentity(BaseModel):
    """Simplified GitHub identity info."""

    login: Optional[str] = None
    avatar_url: Optional[str] = Field(None, alias="account_avatar_url")
    connected_at: Optional[datetime] = None


class AdminUserResponse(BaseModel):
    """User response for admin endpoints."""

    id: PyObjectIdStr = Field(..., alias="_id")
    email: str
    name: Optional[str] = None
    role: Literal["admin", "user"]
    created_at: datetime
    is_banned: bool = Field(default=False)
    banned_at: Optional[datetime] = None
    github: Optional[GithubIdentity] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AdminUserListResponse(BaseModel):
    """Response with list of users."""

    items: List[AdminUserResponse]
    total: int
    page: int = 1
    page_size: int = 20


class AdminUserUpdateRequest(BaseModel):
    """Request to update user profile."""

    email: Optional[str] = Field(None, description="New email address")
    name: Optional[str] = Field(None, description="New display name")

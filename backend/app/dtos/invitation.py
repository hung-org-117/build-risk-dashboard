"""
Invitation DTOs - Request/Response models for invitation API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class InvitationCreateRequest(BaseModel):
    """Request to create a new invitation."""

    email: EmailStr = Field(..., description="Email of the user to invite")
    role: str = Field(default="guest", pattern="^(guest)$")


class InvitationResponse(BaseModel):
    """Invitation response model."""

    id: str = Field(..., alias="_id")
    email: str
    status: str
    role: str
    invited_by: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        populate_by_name = True


class InvitationListResponse(BaseModel):
    """List of invitations response."""

    items: List[InvitationResponse]
    total: int

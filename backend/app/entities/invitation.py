"""
Invitation Entity - Stores user invitation tokens for non-org members.
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from pydantic import Field
import secrets

from .base import BaseEntity, PyObjectId


class InvitationStatus(str, Enum):
    """Invitation status enum."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Invitation(BaseEntity):
    """
    User invitation for non-org GitHub members.

    Allows admin to invite users who are not members of the GitHub organization.
    When they login via GitHub OAuth, the system checks for valid invitation.
    """

    # Invitation target (at least one required)
    email: str = Field(..., description="Email address of the invited user")
    github_username: Optional[str] = Field(
        None, description="GitHub username (optional)"
    )

    # Invitation state
    status: InvitationStatus = InvitationStatus.PENDING
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Role assignment
    role: str = Field(default="user", description="Role to assign when accepted")

    # Metadata
    invited_by: PyObjectId = Field(
        ..., description="Admin user ID who created invitation"
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )

    # Acceptance tracking
    accepted_at: Optional[datetime] = None
    accepted_by_user_id: Optional[PyObjectId] = None

    class Config:
        use_enum_values = True

    def is_valid(self) -> bool:
        """Check if invitation is still valid (pending and not expired)."""
        if self.status != InvitationStatus.PENDING:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def accept(self, user_id: PyObjectId) -> "Invitation":
        """Mark invitation as accepted."""
        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = datetime.now(timezone.utc)
        self.accepted_by_user_id = user_id
        return self

    def revoke(self) -> "Invitation":
        """Revoke the invitation."""
        self.status = InvitationStatus.REVOKED
        return self

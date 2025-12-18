"""
Invitation Service - Business logic for user invitations.
"""

from __future__ import annotations

import logging
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.config import settings
from app.dtos.invitation import (
    InvitationCreateRequest,
    InvitationResponse,
    InvitationListResponse,
)
from app.entities.invitation import Invitation
from app.repositories.invitation import InvitationRepository
from app.services.notification_service import get_notification_manager

logger = logging.getLogger(__name__)


class InvitationService:
    """Service for managing user invitations."""

    def __init__(self, db: Database):
        self.db = db
        self.repo = InvitationRepository(db)

    def _to_response(self, invitation: Invitation) -> InvitationResponse:
        """Convert entity to response DTO."""
        return InvitationResponse(
            _id=str(invitation.id),
            email=invitation.email,
            github_username=invitation.github_username,
            status=invitation.status,
            role=invitation.role,
            invited_by=str(invitation.invited_by),
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_at=invitation.created_at,
        )

    def list_invitations(
        self, status_filter: Optional[str] = None
    ) -> InvitationListResponse:
        """List all invitations with optional status filter."""
        # Mark expired invitations first
        self.repo.mark_expired()

        invitations = self.repo.list_all(status=status_filter)
        return InvitationListResponse(
            items=[self._to_response(inv) for inv in invitations],
            total=len(invitations),
        )

    def create_invitation(
        self,
        payload: InvitationCreateRequest,
        admin_id: ObjectId,
    ) -> InvitationResponse:
        """
        Create a new invitation and send email notification.

        Args:
            payload: Invitation details
            admin_id: ID of the admin creating the invitation

        Returns:
            Created invitation response

        Raises:
            HTTPException: If invitation already exists for this email
        """
        # Check if pending invitation already exists
        existing = self.repo.find_valid_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A pending invitation already exists for {payload.email}",
            )

        # Check if user already exists in system
        existing_user = self.db.users.find_one(
            {"email": {"$regex": f"^{payload.email}$", "$options": "i"}}
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {payload.email} already exists in the system",
            )

        # Create invitation
        invitation = Invitation(
            email=payload.email,
            github_username=payload.github_username,
            role=payload.role,
            invited_by=admin_id,
        )

        saved = self.repo.insert_one(invitation)

        # Send invitation email
        self._send_invitation_email(saved)

        logger.info(f"Created invitation for {payload.email} by admin {admin_id}")
        return self._to_response(saved)

    def revoke_invitation(self, invitation_id: str) -> InvitationResponse:
        """
        Revoke a pending invitation.

        Args:
            invitation_id: ID of invitation to revoke

        Returns:
            Updated invitation response

        Raises:
            HTTPException: If invitation not found or not pending
        """
        invitation = self.repo.revoke_invitation(invitation_id)
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found or already used/revoked",
            )

        logger.info(f"Revoked invitation {invitation_id}")
        return self._to_response(invitation)

    def get_invitation(self, invitation_id: str) -> InvitationResponse:
        """Get invitation by ID."""
        invitation = self.repo.find_by_id(ObjectId(invitation_id))
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )
        return self._to_response(invitation)

    def accept_invitation(
        self, invitation: Invitation, user_id: ObjectId
    ) -> Invitation:
        """
        Accept an invitation (called from OAuth flow).

        Args:
            invitation: The invitation to accept
            user_id: ID of the user accepting

        Returns:
            Updated invitation
        """
        accepted = self.repo.accept_invitation(str(invitation.id), user_id)
        logger.info(f"Invitation {invitation.id} accepted by user {user_id}")
        return accepted

    def _send_invitation_email(self, invitation: Invitation) -> None:
        """Send invitation email to the invited user."""
        try:
            manager = get_notification_manager(self.db)

            invite_url = f"{settings.FRONTEND_BASE_URL}/login?invite={invitation.token}"
            expires_str = invitation.expires_at.strftime("%Y-%m-%d %H:%M UTC")

            subject = f"You've been invited to {settings.APP_NAME}"
            body = f"""Hello,

You have been invited to join {settings.APP_NAME}.

To accept this invitation and create your account, please visit:
{invite_url}

This invitation will expire on {expires_str}.

You will need to login with your GitHub account to complete the registration.

If you did not expect this invitation, you can safely ignore this email.

Best regards,
The {settings.APP_NAME} Team
"""

            html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>You've been invited to {settings.APP_NAME}</h2>
    <p>Hello,</p>
    <p>You have been invited to join <strong>{settings.APP_NAME}</strong>.</p>
    <p>
        <a href="{invite_url}" 
           style="display: inline-block; padding: 12px 24px; background-color: #2563eb; 
                  color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">
            Accept Invitation
        </a>
    </p>
    <p style="color: #666; font-size: 0.9em;">
        This invitation will expire on <strong>{expires_str}</strong>.
    </p>
    <p style="color: #666; font-size: 0.9em;">
        You will need to login with your GitHub account to complete the registration.
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 0.8em;">
        If you did not expect this invitation, you can safely ignore this email.
    </p>
</body>
</html>
"""

            manager.send_gmail(
                subject=subject,
                body=body,
                html_body=html_body,
                recipients=[invitation.email],
            )
            logger.info(f"Invitation email sent to {invitation.email}")

        except Exception as e:
            # Don't fail invitation creation if email fails
            logger.error(f"Failed to send invitation email to {invitation.email}: {e}")


def find_valid_invitation(
    db: Database,
    email: Optional[str] = None,
    github_username: Optional[str] = None,
) -> Optional[Invitation]:
    """
    Helper function to find valid invitation (for use in OAuth flow).

    Args:
        db: Database connection
        email: User's email
        github_username: User's GitHub login

    Returns:
        Valid invitation if found
    """
    repo = InvitationRepository(db)
    return repo.find_valid_invitation(email=email, github_username=github_username)

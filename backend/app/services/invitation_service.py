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
    InvitationListResponse,
    InvitationResponse,
)
from app.entities.invitation import Invitation
from app.repositories.invitation import InvitationRepository
from app.repositories.user import UserRepository
from app.services.email_templates import render_email
from app.services.notification_service import get_notification_manager

logger = logging.getLogger(__name__)


class InvitationService:
    """Service for managing user invitations."""

    def __init__(self, db: Database):
        self.db = db
        self.repo = InvitationRepository(db)
        self.user_repo = UserRepository(db)

    def _to_response(self, invitation: Invitation) -> InvitationResponse:
        """Convert entity to response DTO."""
        return InvitationResponse(
            _id=str(invitation.id),
            email=invitation.email,
            status=invitation.status,
            role=invitation.role,
            invited_by=str(invitation.invited_by),
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_at=invitation.created_at,
        )

    def list_invitations(self, status_filter: Optional[str] = None) -> InvitationListResponse:
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
        existing_user = self.user_repo.find_by_email(payload.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {payload.email} already exists in the system",
            )

        # Create invitation
        invitation = Invitation(
            email=payload.email,
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

    def accept_invitation(self, invitation: Invitation, user_id: ObjectId) -> Invitation:
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

            # Determine subject
            subject = f"You've been invited to {settings.APP_NAME}"

            # Prepare context for template
            context = {
                "app_name": settings.APP_NAME,
                "invite_url": invite_url,
                "expires_str": expires_str,
            }

            # Render HTML body using Handlebars template
            html_body = render_email("invitation", context, subject=subject)

            manager.send_gmail(
                subject=subject,
                html_body=html_body,
                to_recipients=[invitation.email],
            )
            logger.info(f"Invitation email sent to {invitation.email}")

        except Exception as e:
            # Don't fail invitation creation if email fails
            logger.error(f"Failed to send invitation email to {invitation.email}: {e}")


def find_valid_invitation(
    db: Database,
    email: str,
) -> Optional[Invitation]:
    """
    Helper function to find valid invitation (for use in OAuth flow).

    Args:
        db: Database connection
        email: User's email

    Returns:
        Valid invitation if found
    """
    repo = InvitationRepository(db)
    return repo.find_valid_invitation(email=email)

"""
Invitation Repository - Database operations for user invitations.
"""

from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId

from app.entities.invitation import Invitation, InvitationStatus

from .base import BaseRepository


class InvitationRepository(BaseRepository[Invitation]):
    """Repository for Invitation entities."""

    def __init__(self, db):
        super().__init__(db, "invitations", Invitation)

    def find_by_token(self, token: str) -> Optional[Invitation]:
        """Find invitation by unique token."""
        return self.find_one({"token": token})

    def find_valid_by_email(self, email: str) -> Optional[Invitation]:
        """Find a valid (pending, not expired) invitation by email."""
        now = datetime.now(timezone.utc)
        return self.find_one(
            {
                "email": {"$regex": f"^{email}$", "$options": "i"},
                "status": InvitationStatus.PENDING.value,
                "expires_at": {"$gt": now},
            }
        )

    def find_valid_invitation(self, email: str) -> Optional[Invitation]:
        """
        Find a valid invitation matching email.

        Args:
            email: User's email address

        Returns:
            Valid invitation if found, None otherwise
        """
        return self.find_valid_by_email(email)

    def list_all(self, status: Optional[str] = None, limit: int = 100) -> List[Invitation]:
        """List invitations with optional status filter."""
        query = {}
        if status:
            query["status"] = status

        return self.find_many(query, sort=[("created_at", -1)], limit=limit)

    def list_pending(self) -> List[Invitation]:
        """List all pending invitations."""
        return self.list_all(status=InvitationStatus.PENDING.value)

    def mark_expired(self) -> int:
        """Mark all expired pending invitations. Returns count of marked."""
        now = datetime.now(timezone.utc)
        result = self.collection.update_many(
            {
                "status": InvitationStatus.PENDING.value,
                "expires_at": {"$lt": now},
            },
            {
                "$set": {
                    "status": InvitationStatus.EXPIRED.value,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count

    def accept_invitation(self, invitation_id: str, user_id: ObjectId) -> Optional[Invitation]:
        """Mark invitation as accepted."""
        now = datetime.now(timezone.utc)
        result = self.collection.find_one_and_update(
            {"_id": self._to_object_id(invitation_id)},
            {
                "$set": {
                    "status": InvitationStatus.ACCEPTED.value,
                    "accepted_at": now,
                    "accepted_by_user_id": user_id,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        return Invitation(**result) if result else None

    def revoke_invitation(self, invitation_id: str) -> Optional[Invitation]:
        """Revoke (cancel) an invitation."""
        now = datetime.now(timezone.utc)
        result = self.collection.find_one_and_update(
            {
                "_id": self._to_object_id(invitation_id),
                "status": InvitationStatus.PENDING.value,
            },
            {
                "$set": {
                    "status": InvitationStatus.REVOKED.value,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        return Invitation(**result) if result else None

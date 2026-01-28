"""Admin User Management Service."""

from __future__ import annotations

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos.admin_user import (
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    GithubIdentity,
)
from app.repositories.oauth_identity import OAuthIdentityRepository
from app.repositories.user import UserRepository


class AdminUserService:
    """Service for admin user management operations."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.oauth_identity_repo = OAuthIdentityRepository(db)

    def _to_response(self, user, github_identity=None) -> AdminUserResponse:
        """Convert User entity to AdminUserResponse."""
        github = None
        if github_identity:
            github = GithubIdentity(
                login=github_identity.account_login,
                account_avatar_url=getattr(github_identity, "account_avatar_url", None),
                connected_at=getattr(github_identity, "connected_at", None),
            )

        return AdminUserResponse(
            _id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            created_at=user.created_at,
            is_banned=getattr(user, "is_banned", False),
            banned_at=getattr(user, "banned_at", None),
            github=github,
        )

    def list_users(
        self, search: str = None, page: int = 1, page_size: int = 20
    ) -> AdminUserListResponse:
        """List all users (UC6: View User List)."""
        skip = (page - 1) * page_size
        users = self.user_repo.list_all(search=search, skip=skip, limit=page_size)
        total = self.user_repo.count_all(search=search)

        # Batch fetch GitHub identities
        user_ids = [u.id for u in users]
        identities = self.oauth_identity_repo.find_by_user_ids(
            user_ids, provider="github"
        )
        identity_map = {str(i.user_id): i for i in identities}

        return AdminUserListResponse(
            items=[self._to_response(u, identity_map.get(str(u.id))) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_user(self, user_id: str) -> AdminUserResponse:
        """Get user details by ID."""
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        identity = self.oauth_identity_repo.find_by_user_id_and_provider(
            user.id, provider="github"
        )
        return self._to_response(user, identity)

    def update_user(
        self, user_id: str, payload: AdminUserUpdateRequest
    ) -> AdminUserResponse:
        """Update user profile."""
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        user = self.user_repo.update_user(user_id, updates)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return self._to_response(user)

    def delete_user(self, user_id: str, current_admin_id: str) -> None:
        """Ban user account instead of hard delete (UC4: Delete User Account)."""
        # Prevent admin from deleting themselves
        if user_id == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        # Only allow banning regular users, not admins
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot ban admin users. Admins can only be deleted by other admins with proper permission.",
            )

        success = self.user_repo.ban_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Optionally clean up OAuth identities to revoke access tokens
        self.oauth_identity_repo.delete_by_user_id(ObjectId(user_id))

    def unban_user(self, user_id: str) -> AdminUserResponse:
        """Unban a user to restore their login access."""
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Update to unban
        updates = {
            "is_banned": False,
            "banned_at": None,
        }
        updated_user = self.user_repo.update_user(user_id, updates)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unban user",
            )
        return self._to_response(updated_user)

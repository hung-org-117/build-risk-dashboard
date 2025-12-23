"""Admin User Management Service."""

from __future__ import annotations

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos.admin_user import (
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.repositories.oauth_identity import OAuthIdentityRepository
from app.repositories.user import UserRepository


class AdminUserService:
    """Service for admin user management operations."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)
        self.oauth_identity_repo = OAuthIdentityRepository(db)

    def _to_response(self, user) -> AdminUserResponse:
        """Convert User entity to AdminUserResponse."""
        return AdminUserResponse(
            _id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            created_at=user.created_at,
        )

    def list_users(self, search: str = None) -> AdminUserListResponse:
        """List all users (UC6: View User List)."""
        users = self.user_repo.list_all(search=search)
        return AdminUserListResponse(
            items=[self._to_response(u) for u in users],
            total=len(users),
        )

    def get_user(self, user_id: str) -> AdminUserResponse:
        """Get user details by ID."""
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return self._to_response(user)

    def update_user(self, user_id: str, payload: AdminUserUpdateRequest) -> AdminUserResponse:
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
        """Delete user account (UC4: Delete User Account)."""
        # Prevent admin from deleting themselves
        if user_id == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        # Check if this would leave no admins
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if user and user.role == "admin":
            admin_count = self.user_repo.count_admins()
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last admin",
                )

        success = self.user_repo.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Also clean up OAuth identities for this user
        self.oauth_identity_repo.delete_by_user_id(ObjectId(user_id))

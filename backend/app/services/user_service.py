"""User account service using repository pattern"""

from datetime import datetime
from typing import List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos import UserResponse, UserUpdate
from app.entities.oauth_identity import OAuthIdentity
from app.entities.user import User
from app.repositories.oauth_identity import OAuthIdentityRepository
from app.repositories.user import UserRepository

PROVIDER_GITHUB = "github"


def upsert_github_identity(
    db: Database,
    *,
    github_user_id: str,
    email: str,
    name: Optional[str],
    access_token: str,
    refresh_token: Optional[str],
    token_expires_at: Optional[datetime],
    scopes: Optional[str],
    account_login: Optional[str] = None,
    account_name: Optional[str] = None,
    account_avatar_url: Optional[str] = None,
    connected_at: Optional[datetime] = None,
) -> Tuple[User, OAuthIdentity]:
    """Upsert a GitHub identity and associated user"""
    oauth_repo = OAuthIdentityRepository(db)
    return oauth_repo.upsert_github_identity(
        github_user_id=github_user_id,
        email=email,
        name=name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        scopes=scopes,
        account_login=account_login,
        account_name=account_name,
        account_avatar_url=account_avatar_url,
        connected_at=connected_at,
    )


class UserService:
    def __init__(self, db: Database):
        self.db = db

    def list_users(self) -> List[UserResponse]:
        """List all users"""
        user_repo = UserRepository(self.db)
        documents = user_repo.list_all()
        return [UserResponse.model_validate(doc) for doc in documents]

    def get_user_by_id(self, user_id: str) -> UserResponse:
        """Get user by ID"""
        user_doc = self.db.users.find_one({"_id": ObjectId(user_id)})

        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse.model_validate(user_doc)

    def update_user(self, user_id: str, update_data: UserUpdate) -> UserResponse:
        """Update user details"""
        user_repo = UserRepository(self.db)

        # Create update dict, excluding None values
        # Create update dict using only set fields (allows setting to None)
        update_dict = update_data.model_dump(exclude_unset=True)

        if not update_dict:
            # If nothing to update, just return current user
            return self.get_user_by_id(user_id)

        user_repo.update(user_id, update_dict)
        return self.get_user_by_id(user_id)

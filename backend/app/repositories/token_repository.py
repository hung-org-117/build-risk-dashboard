"""Repository for GitHub tokens (github_tokens collection)."""

from typing import List, Optional
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.database import Database

from app.repositories.base import BaseRepository
from app.entities.github_token import GithubToken, GitHubTokenStatus


class TokenRepository(BaseRepository[GithubToken]):
    """Repository for github_tokens collection."""

    def __init__(self, db: Database):
        super().__init__(db, "github_tokens", GithubToken)

    def find_active(self) -> List[GithubToken]:
        """Find all active tokens."""
        return self.find_many(
            {"status": {"$ne": GitHubTokenStatus.DISABLED}},
            sort=[("rate_limit_remaining", -1)],
        )

    def find_by_hash(self, token_hash: str) -> Optional[GithubToken]:
        """Find token by hash."""
        return self.find_one({"token_hash": token_hash})

    def update_rate_limit(
        self,
        token_id: str | ObjectId,
        rate_limit_remaining: int,
        rate_limit_limit: int,
        rate_limit_reset_at: datetime,
    ) -> Optional[GithubToken]:
        """Update rate limit info for a token."""
        now = datetime.now(timezone.utc)

        # Determine status based on remaining
        status = GitHubTokenStatus.ACTIVE
        if rate_limit_remaining == 0:
            status = GitHubTokenStatus.RATE_LIMITED

        return self.update_one(
            token_id,
            {
                "rate_limit_remaining": rate_limit_remaining,
                "rate_limit_limit": rate_limit_limit,
                "rate_limit_reset_at": rate_limit_reset_at,
                "last_validated_at": now,
                "updated_at": now,
                "status": status,
                "validation_error": None,
            },
        )

    def mark_invalid(
        self, token_id: str | ObjectId, error: str = "Token is invalid or revoked"
    ) -> Optional[GithubToken]:
        """Mark a token as invalid."""
        now = datetime.now(timezone.utc)
        return self.update_one(
            token_id,
            {
                "status": GitHubTokenStatus.INVALID,
                "validation_error": error,
                "last_validated_at": now,
                "updated_at": now,
            },
        )

    def set_status(
        self, token_id: str | ObjectId, status: str
    ) -> Optional[GithubToken]:
        """Set token status."""
        now = datetime.now(timezone.utc)
        return self.update_one(
            token_id,
            {
                "status": status,
                "updated_at": now,
            },
        )

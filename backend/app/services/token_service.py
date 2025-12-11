"""Service for GitHub token management."""

from typing import List, Optional, Tuple
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo.database import Database

from app.repositories.token_repository import TokenRepository
from app.entities.github_token import GitHubTokenStatus
from app.services.github.github_token_manager import (
    add_public_token,
    remove_public_token,
    update_public_token,
    list_public_tokens,
    get_public_token_by_id,
    get_tokens_pool_status,
    verify_github_token,
    get_token_rate_limit,
    get_raw_token_from_cache,
    PublicTokenStatus,
)


class TokenService:
    """Service for GitHub token management operations."""

    def __init__(self, db: Database):
        self.db = db
        self.token_repo = TokenRepository(db)

    async def refresh_all_tokens(self) -> dict:
        """
        Refresh rate limit info for all tokens by querying GitHub API.

        Uses tokens from in-memory cache (seeded from GITHUB_TOKENS env var).
        """
        tokens = self.token_repo.find_active()
        results = []
        refreshed = 0
        failed = 0

        for token in tokens:
            token_id = str(token.id)
            token_hash = token.token_hash

            if not token_hash:
                results.append(
                    {"id": token_id, "success": False, "error": "No token hash"}
                )
                failed += 1
                continue

            # Get raw token from cache
            raw_token = get_raw_token_from_cache(token_hash)
            if not raw_token:
                results.append(
                    {
                        "id": token_id,
                        "success": False,
                        "error": "Token not in cache (add to GITHUB_TOKENS env var)",
                    }
                )
                failed += 1
                continue

            # Query GitHub API for rate limit
            rate_limit_info = await get_token_rate_limit(raw_token)

            if rate_limit_info:
                self.token_repo.update_rate_limit(
                    token_id,
                    rate_limit_remaining=rate_limit_info["remaining"],
                    rate_limit_limit=rate_limit_info["limit"],
                    rate_limit_reset_at=rate_limit_info["reset_at"],
                )

                results.append(
                    {
                        "id": token_id,
                        "success": True,
                        "remaining": rate_limit_info["remaining"],
                        "limit": rate_limit_info["limit"],
                    }
                )
                refreshed += 1
            else:
                # Token might be invalid
                self.token_repo.mark_invalid(token_id, "Failed to get rate limit")
                results.append(
                    {
                        "id": token_id,
                        "success": False,
                        "error": "Failed to get rate limit from GitHub API",
                    }
                )
                failed += 1

        return {"refreshed": refreshed, "failed": failed, "results": results}

    def list_tokens(self, include_disabled: bool = False) -> dict:
        """List all GitHub tokens (masked, without actual token values)."""
        tokens = list_public_tokens(self.db, include_disabled=include_disabled)
        return {"items": tokens, "total": len(tokens)}

    def get_pool_status(self) -> dict:
        """Get overall status of the token pool."""
        return get_tokens_pool_status(self.db)

    def create_token(self, token: str, label: str = "") -> dict:
        """Add a new GitHub token to the pool."""
        success, result, error_type = add_public_token(
            self.db,
            token=token,
            label=label,
        )

        if not success:
            if error_type == "duplicate_error":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=result,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result,
            )

        # Get the created token info
        token_info = get_public_token_by_id(self.db, result)
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created token",
            )

        return token_info

    def get_token(self, token_id: str) -> dict:
        """Get details of a specific token."""
        token_info = get_public_token_by_id(self.db, token_id)
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found",
            )
        return token_info

    def update_token(
        self,
        token_id: str,
        label: Optional[str] = None,
        token_status: Optional[str] = None,
    ) -> dict:
        """Update a token's label or status."""
        # Check token exists
        existing = get_public_token_by_id(self.db, token_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found",
            )

        # Validate status if provided
        if token_status is not None:
            if token_status not in [
                PublicTokenStatus.ACTIVE,
                PublicTokenStatus.DISABLED,
            ]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be '{PublicTokenStatus.ACTIVE}' or '{PublicTokenStatus.DISABLED}'",
                )

        success = update_public_token(
            self.db,
            token_id=token_id,
            label=label,
            status=token_status,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update token",
            )

        # Return updated token
        return get_public_token_by_id(self.db, token_id)

    def delete_token(self, token_id: str) -> bool:
        """Remove a token from the pool."""
        success = remove_public_token(self.db, token_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found",
            )
        return True

    async def verify_token(self, token_id: str, raw_token: str) -> dict:
        """Verify a token is still valid by calling GitHub API."""
        # Check token exists in database
        existing = get_public_token_by_id(self.db, token_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found",
            )

        if not raw_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="raw_token is required for verification",
            )

        # Validate the provided token
        is_valid, rate_limit_info = await verify_github_token(raw_token)

        if is_valid:
            # Update token status in database
            if rate_limit_info:
                self.token_repo.update_rate_limit(
                    token_id,
                    rate_limit_remaining=rate_limit_info["remaining"],
                    rate_limit_limit=rate_limit_info["limit"],
                    rate_limit_reset_at=rate_limit_info["reset_at"],
                )
            else:
                self.token_repo.set_status(token_id, GitHubTokenStatus.ACTIVE)

            return {
                "valid": True,
                "rate_limit_remaining": (
                    rate_limit_info["remaining"] if rate_limit_info else None
                ),
                "rate_limit_limit": (
                    rate_limit_info["limit"] if rate_limit_info else None
                ),
            }
        else:
            # Mark as invalid
            self.token_repo.mark_invalid(token_id)

            return {
                "valid": False,
                "error": "Token is invalid or revoked",
            }

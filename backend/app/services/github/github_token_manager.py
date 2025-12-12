"""GitHub token management utilities.

This module provides utility functions for token hashing, masking,
and verification against GitHub API.

NOTE: Token storage is now handled by Redis pool (redis_token_pool.py).
This module only contains utility functions.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.config import settings

GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_RATE_LIMIT_URL = "https://api.github.com/rate_limit"


# ============================================================================
# Token Status Constants
# ============================================================================


class GitHubTokenStatus:
    """GitHub token status indicators."""

    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MISSING = "missing"
    INVALID = "invalid"


# ============================================================================
# Token Hashing & Masking Utilities
# ============================================================================


def hash_token(token: str) -> str:
    """Create SHA-256 hash of a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def mask_token(token: str) -> str:
    """Mask token to show only last 4 characters."""
    if not token or len(token) <= 4:
        return "****"
    return f"****{token[-4:]}"


# ============================================================================
# Token Validation Functions
# ============================================================================


async def verify_github_token(access_token: str) -> Tuple[bool, Optional[dict]]:
    """
    Verify a GitHub token and get rate limit info.

    Returns:
        Tuple of (is_valid, rate_limit_info)
        rate_limit_info contains: remaining, limit, reset_at
    """
    if not access_token:
        return False, None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GITHUB_USER_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                },
            )

            rate_limit_info = None
            remaining = response.headers.get("X-RateLimit-Remaining")
            limit = response.headers.get("X-RateLimit-Limit")
            reset = response.headers.get("X-RateLimit-Reset")

            if remaining is not None:
                rate_limit_info = {
                    "remaining": int(remaining),
                    "limit": int(limit) if limit else 5000,
                    "reset_at": (
                        datetime.fromtimestamp(int(reset), tz=timezone.utc)
                        if reset
                        else None
                    ),
                }

            return response.status_code == 200, rate_limit_info
    except Exception:
        return False, None


async def get_token_rate_limit(access_token: str) -> Optional[dict]:
    """Get rate limit info for a token without making an authenticated request."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GITHUB_RATE_LIMIT_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                },
            )
            if response.status_code == 200:
                data = response.json()
                core = data.get("resources", {}).get("core", {})
                return {
                    "remaining": core.get("remaining", 0),
                    "limit": core.get("limit", 5000),
                    "reset_at": datetime.fromtimestamp(
                        core.get("reset", 0), tz=timezone.utc
                    ),
                }
    except Exception:
        pass
    return None


# ============================================================================
# User OAuth Token Management
# ============================================================================


async def check_github_token_status(
    db: Database, user_id: ObjectId, verify_with_api: bool = False
) -> Tuple[str, Optional[dict]]:
    identity = db.oauth_identities.find_one({"user_id": user_id, "provider": "github"})

    if not identity:
        return GitHubTokenStatus.MISSING, None

    access_token = identity.get("access_token")
    if not access_token:
        return GitHubTokenStatus.MISSING, identity

    # Check if token has explicit expiration time
    token_expires_at = identity.get("token_expires_at")
    if token_expires_at:
        if datetime.now(timezone.utc) >= token_expires_at:
            return GitHubTokenStatus.EXPIRED, identity

    # Optionally verify with GitHub API
    if verify_with_api:
        is_valid, _ = await verify_github_token(access_token)
        if not is_valid:
            return GitHubTokenStatus.REVOKED, identity

    return GitHubTokenStatus.VALID, identity


async def get_valid_github_token(
    db: Database, user_id: ObjectId, verify_with_api: bool = False
) -> str:
    status_code, identity = await check_github_token_status(
        db, user_id, verify_with_api
    )

    if status_code == GitHubTokenStatus.MISSING:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub account not connected. Please connect your GitHub account.",
            headers={"X-Auth-Error": "github_not_connected"},
        )

    if status_code == GitHubTokenStatus.EXPIRED:
        # Mark token as invalid in database
        await mark_github_oauth_token_invalid(db, identity["_id"], reason="expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub token has expired. Please re-authenticate with GitHub.",
            headers={"X-Auth-Error": "github_token_expired"},
        )

    if status_code == GitHubTokenStatus.REVOKED:
        # Mark token as invalid in database
        await mark_github_oauth_token_invalid(db, identity["_id"], reason="revoked")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub token has been revoked. Please re-authenticate with GitHub.",
            headers={"X-Auth-Error": "github_token_revoked"},
        )

    return identity["access_token"]


async def mark_github_oauth_token_invalid(
    db: Database, identity_id: ObjectId, reason: str = "invalid"
) -> None:
    db.oauth_identities.update_one(
        {"_id": identity_id},
        {
            "$set": {
                "token_status": "invalid",
                "token_invalid_reason": reason,
                "token_invalidated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


async def refresh_github_token_if_needed(
    db: Database, user_id: ObjectId
) -> Optional[str]:
    identity = db.oauth_identities.find_one({"user_id": user_id, "provider": "github"})

    if not identity:
        return None

    refresh_token = identity.get("refresh_token")
    if not refresh_token:
        # No refresh token available - user needs to re-authenticate
        return None

    # Check if token is expired
    token_expires_at = identity.get("token_expires_at")
    if not token_expires_at or datetime.now(timezone.utc) < token_expires_at:
        # Token not expired yet
        return identity.get("access_token")

    # Attempt to refresh token
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            response.raise_for_status()
            token_data = response.json()

            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")

            if not new_access_token:
                return None

            # Calculate new expiration time
            new_expires_at = None
            if expires_in:
                new_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )

            # Update token in database
            db.oauth_identities.update_one(
                {"_id": identity["_id"]},
                {
                    "$set": {
                        "access_token": new_access_token,
                        "refresh_token": new_refresh_token or refresh_token,
                        "token_expires_at": new_expires_at,
                        "token_status": "valid",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            return new_access_token

    except Exception:
        # Refresh failed - mark token as invalid
        await mark_github_oauth_token_invalid(
            db, identity["_id"], reason="refresh_failed"
        )
        return None


def requires_github_token(verify_with_api: bool = False):
    async def dependency(user_id: str, db: Database) -> str:
        """Get valid GitHub token or raise exception."""
        return await get_valid_github_token(
            db, ObjectId(user_id), verify_with_api=verify_with_api
        )

    return dependency

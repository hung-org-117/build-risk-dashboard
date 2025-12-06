"""
Redis-based GitHub token pool for distributed round-robin token management.

This module provides a thread-safe, multi-process safe token pool using Redis
for state management. Tokens are rotated using atomic Redis operations to ensure
fair distribution across concurrent requests.

Redis Keys:
- github_tokens:raw:{hash} - Raw token value (encrypted or plain)
- github_tokens:pool - Sorted set of token hashes by priority (remaining quota)
- github_tokens:cooldown:{hash} - Cooldown expiry timestamp
- github_tokens:stats:{hash} - Token usage statistics (hash map)
- github_tokens:index - Current round-robin index (atomic counter)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import redis
from pymongo.database import Database

from app.config import settings
from app.core.redis import get_redis
from app.services.github.github_token_manager import (
    hash_token,
    mask_token,
    PublicTokenStatus,
    update_token_rate_limit as db_update_token_rate_limit,
    mark_token_rate_limited as db_mark_token_rate_limited,
)

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_PREFIX = "github_tokens"
KEY_RAW = f"{KEY_PREFIX}:raw"  # Hash -> Raw token
KEY_POOL = f"{KEY_PREFIX}:pool"  # Sorted set by priority
KEY_COOLDOWN = f"{KEY_PREFIX}:cooldown"  # Hash -> cooldown expiry
KEY_STATS = f"{KEY_PREFIX}:stats"  # Hash -> usage stats
KEY_INDEX = f"{KEY_PREFIX}:index"  # Round-robin counter


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_ts() -> float:
    return _now().timestamp()


class RedisTokenPool:
    """
    Redis-backed token pool with atomic round-robin and rate limit tracking.

    Features:
    - Atomic token acquisition across multiple processes/workers
    - Automatic cooldown for rate-limited tokens
    - Priority-based selection (tokens with more remaining quota first)
    - Persistent across restarts (tokens stored in Redis)
    """

    def __init__(self, db: Database | None = None):
        """
        Initialize Redis token pool.

        Args:
            db: MongoDB database for syncing stats back (optional)
        """
        self._redis: redis.Redis = get_redis()
        self._db = db

    def add_token(self, raw_token: str, label: str = "") -> str:
        """
        Add a token to the Redis pool.

        Args:
            raw_token: The actual GitHub token
            label: Optional label for the token

        Returns:
            Token hash
        """
        token_hash = hash_token(raw_token)

        # Store raw token
        self._redis.hset(KEY_RAW, token_hash, raw_token)

        # Add to pool with default priority (5000 = full quota)
        self._redis.zadd(KEY_POOL, {token_hash: 5000})

        # Initialize stats
        self._redis.hset(
            f"{KEY_STATS}:{token_hash}",
            mapping={
                "label": label or f"Token {mask_token(raw_token)}",
                "total_requests": 0,
                "last_used_at": "",
                "status": PublicTokenStatus.ACTIVE,
            },
        )

        logger.info(f"Added token {mask_token(raw_token)} to Redis pool")
        return token_hash

    def remove_token(self, token_hash: str) -> bool:
        """Remove a token from the pool."""
        pipe = self._redis.pipeline()
        pipe.hdel(KEY_RAW, token_hash)
        pipe.zrem(KEY_POOL, token_hash)
        pipe.delete(f"{KEY_STATS}:{token_hash}")
        pipe.delete(f"{KEY_COOLDOWN}:{token_hash}")
        results = pipe.execute()
        return results[0] > 0

    def acquire_token(self) -> Tuple[str, str]:
        """
        Acquire an available token using atomic round-robin.

        Returns:
            Tuple of (token_hash, raw_token)

        Raises:
            GithubAllRateLimitError if no tokens available
        """
        from app.services.github.exceptions import GithubAllRateLimitError

        now_ts = _now_ts()

        # Get all tokens sorted by priority (highest remaining quota first)
        token_hashes = self._redis.zrevrange(KEY_POOL, 0, -1)

        if not token_hashes:
            raise GithubAllRateLimitError(
                "No GitHub tokens configured in Redis pool.",
                retry_after=None,
            )

        # Try to find an available token
        earliest_cooldown = None

        for token_hash in token_hashes:
            # Check cooldown
            cooldown_until = self._redis.get(f"{KEY_COOLDOWN}:{token_hash}")

            if cooldown_until:
                cooldown_ts = float(cooldown_until)
                if cooldown_ts > now_ts:
                    # Still on cooldown
                    if earliest_cooldown is None or cooldown_ts < earliest_cooldown:
                        earliest_cooldown = cooldown_ts
                    continue
                else:
                    # Cooldown expired, remove it
                    self._redis.delete(f"{KEY_COOLDOWN}:{token_hash}")

            # Token is available, get raw token
            raw_token = self._redis.hget(KEY_RAW, token_hash)

            if not raw_token:
                # Token hash exists but raw token missing, skip
                continue

            # Update usage stats atomically
            pipe = self._redis.pipeline()
            pipe.hincrby(f"{KEY_STATS}:{token_hash}", "total_requests", 1)
            pipe.hset(f"{KEY_STATS}:{token_hash}", "last_used_at", _now().isoformat())
            pipe.execute()

            return token_hash, raw_token

        # All tokens on cooldown
        retry_after = None
        if earliest_cooldown:
            retry_after = datetime.fromtimestamp(earliest_cooldown, tz=timezone.utc)

        raise GithubAllRateLimitError(
            "All GitHub tokens hit rate limits. Please wait before retrying.",
            retry_after=retry_after,
        )

    def update_rate_limit(
        self,
        token_hash: str,
        remaining: int,
        limit: int,
        reset_at: datetime,
    ) -> None:
        """
        Update rate limit info for a token after an API request.

        Args:
            token_hash: Token hash
            remaining: Remaining API requests
            limit: Total rate limit
            reset_at: When rate limit resets
        """
        # Update priority in sorted set (remaining quota)
        self._redis.zadd(KEY_POOL, {token_hash: remaining})

        # Update stats
        self._redis.hset(
            f"{KEY_STATS}:{token_hash}",
            mapping={
                "rate_limit_remaining": remaining,
                "rate_limit_limit": limit,
                "rate_limit_reset_at": reset_at.isoformat(),
            },
        )

        # If remaining is 0, set cooldown
        if remaining == 0:
            self._redis.setex(
                f"{KEY_COOLDOWN}:{token_hash}",
                int((reset_at - _now()).total_seconds()) + 5,  # +5 buffer
                str(reset_at.timestamp()),
            )
            self._redis.hset(
                f"{KEY_STATS}:{token_hash}", "status", PublicTokenStatus.RATE_LIMITED
            )
        else:
            self._redis.hset(
                f"{KEY_STATS}:{token_hash}", "status", PublicTokenStatus.ACTIVE
            )

        # Sync to MongoDB if available
        if self._db:
            try:
                db_update_token_rate_limit(
                    self._db, token_hash, remaining, limit, reset_at
                )
            except Exception as e:
                logger.warning(f"Failed to sync rate limit to MongoDB: {e}")

    def mark_rate_limited(
        self,
        token_hash: str,
        reset_at: datetime | None = None,
    ) -> None:
        """Mark a token as rate limited."""
        if reset_at is None:
            reset_at = _now() + timedelta(minutes=60)

        # Set priority to 0 (lowest)
        self._redis.zadd(KEY_POOL, {token_hash: 0})

        # Set cooldown
        ttl = max(1, int((reset_at - _now()).total_seconds()))
        self._redis.setex(
            f"{KEY_COOLDOWN}:{token_hash}",
            ttl,
            str(reset_at.timestamp()),
        )

        # Update stats
        self._redis.hset(
            f"{KEY_STATS}:{token_hash}",
            mapping={
                "status": PublicTokenStatus.RATE_LIMITED,
                "rate_limit_remaining": 0,
                "rate_limit_reset_at": reset_at.isoformat(),
            },
        )

        # Sync to MongoDB
        if self._db:
            try:
                db_mark_token_rate_limited(self._db, token_hash, reset_at)
            except Exception as e:
                logger.warning(f"Failed to sync rate limit to MongoDB: {e}")

    def get_pool_status(self) -> Dict:
        """Get overall status of the token pool."""
        token_hashes = self._redis.zrevrange(KEY_POOL, 0, -1, withscores=True)

        now_ts = _now_ts()
        total = len(token_hashes)
        active = 0
        rate_limited = 0
        total_remaining = 0
        next_reset = None

        for token_hash, score in token_hashes:
            remaining = int(score)
            total_remaining += remaining

            # Check cooldown
            cooldown_until = self._redis.get(f"{KEY_COOLDOWN}:{token_hash}")
            if cooldown_until:
                cooldown_ts = float(cooldown_until)
                if cooldown_ts > now_ts:
                    rate_limited += 1
                    if next_reset is None or cooldown_ts < next_reset:
                        next_reset = cooldown_ts
                    continue

            active += 1

        return {
            "total_tokens": total,
            "active_tokens": active,
            "rate_limited_tokens": rate_limited,
            "invalid_tokens": 0,
            "disabled_tokens": 0,
            "estimated_requests_available": total_remaining,
            "next_reset_at": (
                datetime.fromtimestamp(next_reset, tz=timezone.utc).isoformat()
                if next_reset
                else None
            ),
            "pool_healthy": active > 0,
        }

    def get_all_tokens(self) -> List[Dict]:
        """Get all tokens with their stats."""
        token_hashes = self._redis.zrevrange(KEY_POOL, 0, -1, withscores=True)

        result = []
        for token_hash, score in token_hashes:
            stats = self._redis.hgetall(f"{KEY_STATS}:{token_hash}")
            raw_token = self._redis.hget(KEY_RAW, token_hash)

            result.append(
                {
                    "token_hash": token_hash,
                    "masked_token": mask_token(raw_token) if raw_token else "****",
                    "label": stats.get("label", ""),
                    "status": stats.get("status", PublicTokenStatus.ACTIVE),
                    "rate_limit_remaining": int(
                        stats.get("rate_limit_remaining", score)
                    ),
                    "rate_limit_limit": int(stats.get("rate_limit_limit", 5000)),
                    "rate_limit_reset_at": stats.get("rate_limit_reset_at"),
                    "last_used_at": stats.get("last_used_at"),
                    "total_requests": int(stats.get("total_requests", 0)),
                }
            )

        return result

    def sync_from_mongodb(self, db: Database) -> int:
        """
        Sync tokens from MongoDB to Redis.

        This should be called at startup to load tokens from DB.

        Returns:
            Number of tokens synced
        """
        from app.services.github.github_token_manager import get_available_tokens

        # We can't get raw tokens from MongoDB (security), so we need env vars
        from app.config import settings

        tokens = settings.GITHUB_TOKENS or []
        tokens = [t.strip() for t in tokens if t and t.strip()]

        synced = 0
        for token in tokens:
            token_hash = hash_token(token)

            # Check if already in Redis
            if self._redis.hexists(KEY_RAW, token_hash):
                continue

            self.add_token(token)
            synced += 1

        return synced

    def clear_pool(self) -> None:
        """Clear all tokens from Redis pool."""
        # Get all token hashes
        token_hashes = self._redis.zrange(KEY_POOL, 0, -1)

        pipe = self._redis.pipeline()
        pipe.delete(KEY_RAW)
        pipe.delete(KEY_POOL)

        for token_hash in token_hashes:
            pipe.delete(f"{KEY_STATS}:{token_hash}")
            pipe.delete(f"{KEY_COOLDOWN}:{token_hash}")

        pipe.delete(KEY_INDEX)
        pipe.execute()


# Module-level singleton
_redis_pool: RedisTokenPool | None = None


def get_redis_token_pool(db: Database | None = None) -> RedisTokenPool:
    """Get or create the Redis token pool singleton."""
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = RedisTokenPool(db=db)

    return _redis_pool


def seed_tokens_to_redis(db: Database | None = None) -> int:
    """
    Seed tokens from environment variables to Redis pool.

    Should be called at application startup.

    Returns:
        Number of tokens added
    """
    pool = get_redis_token_pool(db)
    return pool.sync_from_mongodb(db) if db else 0

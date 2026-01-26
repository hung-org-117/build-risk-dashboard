"""
Redis-based GitHub token pool for distributed round-robin token management.

This module provides a thread-safe, multi-process safe token pool using Redis
for state management. Tokens are rotated using atomic Redis operations to ensure
fair distribution across concurrent requests.

Redis Keys:
- github_tokens:raw:{hash} - Raw token value
- github_tokens:pool - Sorted set of token hashes by priority (remaining quota)
- github_tokens:cooldown:{hash} - Cooldown expiry timestamp
- github_tokens:stats:{hash} - Token usage statistics (hash map)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import redis

from app.config import settings
from app.core.redis import get_redis
from app.services.github.github_token_manager import hash_token, mask_token

logger = logging.getLogger(__name__)

# Token status constants
TOKEN_STATUS_ACTIVE = "active"
TOKEN_STATUS_RATE_LIMITED = "rate_limited"
TOKEN_STATUS_INVALID = "invalid"
TOKEN_STATUS_DISABLED = "disabled"

# Redis key prefixes
KEY_PREFIX = "github_tokens"
KEY_RAW = f"{KEY_PREFIX}:raw"  # Hash -> Raw token
KEY_POOL = f"{KEY_PREFIX}:pool"  # Sorted set by priority
KEY_COOLDOWN = f"{KEY_PREFIX}:cooldown"  # Hash -> cooldown expiry
KEY_STATS = f"{KEY_PREFIX}:stats"  # Hash -> usage stats


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

    def __init__(self):
        """Initialize Redis token pool."""
        self._redis: redis.Redis = get_redis()

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
                "status": TOKEN_STATUS_ACTIVE,
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
        Acquire an available token using atomic Lua script.

        This is thread-safe and process-safe across multiple Celery workers.
        Tokens are selected by priority (highest remaining quota first).

        Returns:
            Tuple of (token_hash, raw_token)

        Raises:
            GithubAllRateLimitError if no tokens available
        """
        from app.services.github.exceptions import GithubAllRateLimitError

        # Lua script for atomic token acquisition
        # This prevents race conditions where multiple workers grab the same token
        acquire_lua = """
        local pool_key = KEYS[1]
        local cooldown_prefix = KEYS[2]
        local stats_prefix = KEYS[3]
        local raw_key = KEYS[4]
        local now_ts = tonumber(ARGV[1])
        local now_iso = ARGV[2]

        -- Get all tokens sorted by priority (highest remaining quota first)
        local tokens = redis.call('ZREVRANGE', pool_key, 0, -1)

        local earliest_cooldown = nil

        for i, token_hash in ipairs(tokens) do
            local cooldown_key = cooldown_prefix .. ':' .. token_hash
            local cooldown = redis.call('GET', cooldown_key)

            if cooldown then
                local cooldown_ts = tonumber(cooldown)
                if cooldown_ts > now_ts then
                    -- Token is on cooldown, track earliest
                    if not earliest_cooldown or cooldown_ts < earliest_cooldown then
                        earliest_cooldown = cooldown_ts
                    end
                else
                    -- Cooldown expired, clear it
                    redis.call('DEL', cooldown_key)
                    cooldown = nil
                end
            end

            if not cooldown then
                -- Token is available, check if raw token exists
                local raw_token = redis.call('HGET', raw_key, token_hash)
                if raw_token then
                    -- Update stats atomically
                    local stats_key = stats_prefix .. ':' .. token_hash
                    redis.call('HINCRBY', stats_key, 'total_requests', 1)
                    redis.call('HSET', stats_key, 'last_used_at', now_iso)

                    -- Return token_hash and raw_token
                    return {token_hash, raw_token}
                end
            end
        end

        -- No tokens available, return earliest cooldown if any
        if earliest_cooldown then
            return {'__COOLDOWN__', tostring(earliest_cooldown)}
        end

        return nil
        """

        now_ts = _now_ts()
        now_iso = _now().isoformat()

        result = self._redis.eval(
            acquire_lua,
            4,  # Number of KEYS
            KEY_POOL,
            KEY_COOLDOWN,
            KEY_STATS,
            KEY_RAW,
            str(now_ts),
            now_iso,
        )

        if result is None:
            raise GithubAllRateLimitError(
                "No GitHub tokens configured in Redis pool.",
                retry_after=None,
            )

        # Handle bytes from Redis
        if isinstance(result[0], bytes):
            result = [r.decode() if isinstance(r, bytes) else r for r in result]

        if result[0] == "__COOLDOWN__":
            # All tokens on cooldown
            earliest_cooldown = float(result[1])
            retry_after = datetime.fromtimestamp(earliest_cooldown, tz=timezone.utc)
            raise GithubAllRateLimitError(
                "All GitHub tokens hit rate limits. Please wait before retrying.",
                retry_after=retry_after,
            )

        token_hash, raw_token = result[0], result[1]
        return token_hash, raw_token

    def get_best_available_token(
        self, current_token_hash: str, current_remaining: int
    ) -> tuple[str, str] | None:
        """
        Get the best available token if it has more remaining quota than current.

        This enables greedy token selection - always use the token with most quota.

        Args:
            current_token_hash: Hash of the current token
            current_remaining: Remaining quota of current token

        Returns:
            Tuple of (token_hash, raw_token) if a better token exists, None otherwise
        """
        from app.services.github.exceptions import GithubAllRateLimitError

        # Lua script to find best token with more remaining than current
        best_token_lua = """
        local pool_key = KEYS[1]
        local cooldown_prefix = KEYS[2]
        local raw_key = KEYS[3]
        local current_hash = ARGV[1]
        local current_remaining = tonumber(ARGV[2])
        local now_ts = tonumber(ARGV[3])

        -- Get all tokens sorted by priority (highest first)
        local tokens = redis.call('ZREVRANGE', pool_key, 0, -1, 'WITHSCORES')

        for i = 1, #tokens, 2 do
            local token_hash = tokens[i]
            local score = tonumber(tokens[i + 1])

            -- Skip if this is the current token
            if token_hash == current_hash then
                -- Continue to next
            elseif score > current_remaining then
                -- Check if token is on cooldown
                local cooldown_key = cooldown_prefix .. ':' .. token_hash
                local cooldown = redis.call('GET', cooldown_key)

                if cooldown then
                    local cooldown_ts = tonumber(cooldown)
                    if cooldown_ts > now_ts then
                        -- Token is on cooldown, skip
                    else
                        -- Cooldown expired, clear it
                        redis.call('DEL', cooldown_key)
                        cooldown = nil
                    end
                end

                if not cooldown then
                    -- Found a better token
                    local raw_token = redis.call('HGET', raw_key, token_hash)
                    if raw_token then
                        return {token_hash, raw_token, tostring(score)}
                    end
                end
            end
        end

        return nil
        """

        now_ts = _now_ts()

        result = self._redis.eval(
            best_token_lua,
            3,  # Number of KEYS
            KEY_POOL,
            KEY_COOLDOWN,
            KEY_RAW,
            current_token_hash,
            str(current_remaining),
            str(now_ts),
        )

        if result is None:
            return None

        # Handle bytes from Redis
        if isinstance(result[0], bytes):
            result = [r.decode() if isinstance(r, bytes) else r for r in result]

        token_hash, raw_token = result[0], result[1]
        better_remaining = int(result[2]) if len(result) > 2 else 0

        logger.debug(
            f"Found better token: {token_hash[:8]}... with {better_remaining} "
            f"remaining (current has {current_remaining})"
        )
        return token_hash, raw_token

    def update_rate_limit(
        self,
        token_hash: str,
        remaining: int,
        limit: int,
        reset_at: datetime | None,
    ) -> None:
        """
        Update rate limit info for a token after an API request.

        Args:
            token_hash: Token hash
            remaining: Remaining API requests
            limit: Total rate limit
            reset_at: When rate limit resets (can be None if header missing)
        """
        # Update priority in sorted set (remaining quota)
        self._redis.zadd(KEY_POOL, {token_hash: remaining})

        # Update stats
        stats_mapping = {
            "rate_limit_remaining": remaining,
            "rate_limit_limit": limit,
        }
        if reset_at:
            stats_mapping["rate_limit_reset_at"] = reset_at.isoformat()
        self._redis.hset(f"{KEY_STATS}:{token_hash}", mapping=stats_mapping)

        # If remaining is 0, set cooldown
        if remaining == 0:
            if reset_at:
                # Use reset time from header
                cooldown_seconds = (
                    int((reset_at - _now()).total_seconds()) + 5
                )  # +5 buffer
            else:
                # Fallback: 60 minutes cooldown when no reset time available
                cooldown_seconds = 3600
                reset_at = _now() + timedelta(minutes=60)
                logger.warning(
                    f"Token {token_hash[:8]}... rate limited but no reset time, "
                    f"using 60min fallback cooldown"
                )

            self._redis.setex(
                f"{KEY_COOLDOWN}:{token_hash}",
                max(1, cooldown_seconds),  # Ensure at least 1 second TTL
                str(reset_at.timestamp()),
            )
            self._redis.hset(
                f"{KEY_STATS}:{token_hash}", "status", TOKEN_STATUS_RATE_LIMITED
            )
        else:
            # Clear cooldown if it exists - this ensures tokens can be acquired
            # after rate limit resets or when manually synced
            self._redis.delete(f"{KEY_COOLDOWN}:{token_hash}")
            self._redis.hset(f"{KEY_STATS}:{token_hash}", "status", TOKEN_STATUS_ACTIVE)

    def update_rate_limit_from_headers(
        self,
        token_hash: str,
        headers: dict,
    ) -> None:
        """
        Update rate limit info from HTTP response headers.

        Args:
            token_hash: Token hash
            headers: HTTP response headers dict
        """
        remaining = headers.get("X-RateLimit-Remaining")
        limit = headers.get("X-RateLimit-Limit")
        reset = headers.get("X-RateLimit-Reset")

        if remaining is None:
            return

        try:
            remaining_int = int(remaining)
            limit_int = int(limit) if limit else 5000
            reset_dt = (
                datetime.fromtimestamp(int(reset), tz=timezone.utc) if reset else None
            )

            # update_rate_limit now handles None reset_dt gracefully
            self.update_rate_limit(token_hash, remaining_int, limit_int, reset_dt)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")

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
                "status": TOKEN_STATUS_RATE_LIMITED,
                "rate_limit_remaining": 0,
                "rate_limit_reset_at": reset_at.isoformat(),
            },
        )

    def mark_token_invalid(self, token_hash: str) -> None:
        """
        Mark a token as invalid (permanently disabled).

        Args:
            token_hash: Token hash
        """
        # Remove from pool (availability set)
        self._redis.zrem(KEY_POOL, token_hash)

        # Remove raw token to prevent accidental usage (optional, but safer)
        # We keep the hash->raw mapping for now in case we want to audit,
        # but removing from POOL ensures it won't be acquired.
        # self._redis.hdel(KEY_RAW, token_hash)

        # Update stats
        self._redis.hset(
            f"{KEY_STATS}:{token_hash}",
            mapping={
                "status": TOKEN_STATUS_INVALID,
                "error": "Marked invalid (401 Unauthorized)",
            },
        )
        logger.warning(f"Token {token_hash} marked as INVALID and removed from pool")

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
        """Get all tokens with their stats for UI display."""
        token_hashes = self._redis.zrevrange(KEY_POOL, 0, -1, withscores=True)

        result = []
        for token_hash, score in token_hashes:
            # Handle bytes from Redis
            if isinstance(token_hash, bytes):
                token_hash = token_hash.decode()

            stats = self._redis.hgetall(f"{KEY_STATS}:{token_hash}")
            # Handle bytes in stats
            stats = {
                k.decode() if isinstance(k, bytes) else k: (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in stats.items()
            }

            raw_token = self._redis.hget(KEY_RAW, token_hash)
            if isinstance(raw_token, bytes):
                raw_token = raw_token.decode()

            result.append(
                {
                    "id": token_hash[:16],  # Use first 16 chars as ID for UI
                    "token_hash": token_hash,
                    "masked_token": mask_token(raw_token) if raw_token else "****",
                    "label": stats.get("label", ""),
                    "status": stats.get("status", TOKEN_STATUS_ACTIVE),
                    "rate_limit_remaining": int(
                        stats.get("rate_limit_remaining", score) or 0
                    ),
                    "rate_limit_limit": int(
                        stats.get("rate_limit_limit", 5000) or 5000
                    ),
                    "rate_limit_reset_at": stats.get("rate_limit_reset_at"),
                    "last_used_at": stats.get("last_used_at") or None,
                    "total_requests": int(stats.get("total_requests", 0) or 0),
                }
            )

        return result

    def seed_from_env(self) -> int:
        """
        Seed tokens from GITHUB_TOKENS environment variable to Redis pool.

        Should be called at application startup.

        Returns:
            Number of tokens added
        """
        tokens = settings.GITHUB_TOKENS or []
        tokens = [t.strip() for t in tokens if t and t.strip()]

        added = 0
        for token in tokens:
            token_hash = hash_token(token)

            # Check if already in Redis
            if self._redis.hexists(KEY_RAW, token_hash):
                continue

            self.add_token(token)
            added += 1
            logger.info(f"Seeded token {mask_token(token)} to Redis pool")

        return added

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

        pipe.execute()


# Module-level singleton
_redis_pool: RedisTokenPool | None = None


def get_redis_token_pool() -> RedisTokenPool:
    """Get or create the Redis token pool singleton."""
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = RedisTokenPool()
        # Seed tokens from env on first access
        _redis_pool.seed_from_env()

    return _redis_pool


def seed_tokens_to_redis() -> int:
    """
    Seed tokens from GITHUB_TOKENS environment variable to Redis pool.

    Should be called at application startup.

    Returns:
        Number of tokens added
    """
    pool = get_redis_token_pool()
    return pool.seed_from_env()

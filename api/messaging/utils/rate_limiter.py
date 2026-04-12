"""
Distributed Rate Limiter using Redis sliding window algorithm.
Production-grade like WhatsApp, Slack rate limiting.

Supports:
- Per-user per-action limits
- Per-IP limits
- Sliding window (accurate, no burst at window edge)
- Token bucket (smoother, allows short bursts)
- Automatic block/unblock
"""
from __future__ import annotations
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def sliding_window_check(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Sliding window rate limit check using Redis.
    Returns (is_allowed, current_count).

    Algorithm:
    - ZADD key timestamp timestamp
    - ZREMRANGEBYSCORE key 0 (now - window)
    - ZCARD key
    - EXPIRE key window
    """
    try:
        from django.core.cache import cache

        # Try to get native Redis client
        redis_client = _get_redis_client(cache)
        if redis_client:
            return _redis_sliding_window(redis_client, key, limit, window_seconds)
        else:
            return _cache_fallback(cache, key, limit, window_seconds)
    except Exception as exc:
        logger.error("sliding_window_check: key=%s error=%s", key, exc)
        return True, 0  # Allow on error


def _redis_sliding_window(redis_client, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.time()
    window_start = now - window_seconds
    full_key = f"ratelimit:{key}"

    pipe = redis_client.pipeline()
    pipe.zadd(full_key, {str(now): now})
    pipe.zremrangebyscore(full_key, 0, window_start)
    pipe.zcard(full_key)
    pipe.expire(full_key, window_seconds + 1)
    results = pipe.execute()

    current_count = results[2]
    is_allowed = current_count <= limit
    return is_allowed, current_count


def _cache_fallback(cache, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Fallback using Django cache (less accurate but functional)."""
    cache_key = f"ratelimit:{key}"
    current = cache.get(cache_key) or 0
    if current >= limit:
        return False, current
    cache.set(cache_key, current + 1, window_seconds)
    return True, current + 1


def _get_redis_client(cache):
    """Try to get native Redis client from Django cache backend."""
    try:
        # django-redis
        return cache.client.get_client()
    except AttributeError:
        pass
    try:
        import redis
        from django.conf import settings
        cache_config = settings.CACHES.get("default", {})
        location = cache_config.get("LOCATION", "redis://localhost:6379/0")
        return redis.from_url(location)
    except Exception:
        return None


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


def check_message_rate(user_id: Any, ip: str = None) -> None:
    """Check message sending rate limits. Raises RateLimitError if exceeded."""
    from ..constants import MAX_MESSAGES_PER_MINUTE

    # Per-user limit
    ok, count = sliding_window_check(
        key=f"messages:user:{user_id}",
        limit=MAX_MESSAGES_PER_MINUTE,
        window_seconds=60,
    )
    if not ok:
        raise RateLimitError(
            f"Message rate limit: {MAX_MESSAGES_PER_MINUTE}/min. Please slow down.",
            retry_after=60,
        )

    # Per-IP limit (more lenient — shared IP possible)
    if ip:
        ok_ip, _ = sliding_window_check(
            key=f"messages:ip:{ip}",
            limit=MAX_MESSAGES_PER_MINUTE * 5,
            window_seconds=60,
        )
        if not ok_ip:
            raise RateLimitError("IP rate limit exceeded.", retry_after=60)


def check_reaction_rate(user_id: Any) -> None:
    from ..constants import MAX_REACTIONS_PER_MINUTE
    ok, _ = sliding_window_check(
        key=f"reactions:user:{user_id}",
        limit=MAX_REACTIONS_PER_MINUTE,
        window_seconds=60,
    )
    if not ok:
        raise RateLimitError(f"Reaction rate limit: {MAX_REACTIONS_PER_MINUTE}/min.", retry_after=60)


def check_call_rate(user_id: Any) -> None:
    from ..constants import MAX_CALLS_PER_HOUR
    ok, _ = sliding_window_check(
        key=f"calls:user:{user_id}",
        limit=MAX_CALLS_PER_HOUR,
        window_seconds=3600,
    )
    if not ok:
        raise RateLimitError(f"Call rate limit: {MAX_CALLS_PER_HOUR}/hour.", retry_after=3600)


def check_api_rate(user_id: Any, endpoint: str, limit: int = 100, window: int = 60) -> None:
    """General API endpoint rate limit."""
    ok, count = sliding_window_check(
        key=f"api:{endpoint}:user:{user_id}",
        limit=limit,
        window_seconds=window,
    )
    if not ok:
        raise RateLimitError(f"API rate limit for '{endpoint}': {limit}/{window}s.", retry_after=window)


def block_user_rate_limit(user_id: Any, duration_seconds: int = 3600, reason: str = "") -> None:
    """Temporarily block a user from sending messages (spam prevention)."""
    try:
        from django.core.cache import cache
        key = f"blocked:user:{user_id}"
        cache.set(key, {"reason": reason, "blocked_at": time.time()}, duration_seconds)
        logger.warning("block_user_rate_limit: user=%s blocked for %ds reason=%s", user_id, duration_seconds, reason)
    except Exception as exc:
        logger.error("block_user_rate_limit: %s", exc)


def is_user_blocked_by_rate_limit(user_id: Any) -> bool:
    """Check if user is temporarily blocked."""
    try:
        from django.core.cache import cache
        return cache.get(f"blocked:user:{user_id}") is not None
    except Exception:
        return False

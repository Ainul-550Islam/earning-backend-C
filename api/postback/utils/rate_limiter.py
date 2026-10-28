"""
utils/rate_limiter.py – Postback-internal rate limiting using Django cache.

Design:
  • Uses a sliding window counter stored in Django's cache backend.
  • No dependency on the api/rate_limit/ app — postback owns its own limit logic.
  • Per-network key bucketed by 1-minute windows.
  • Burst protection via per-second bucket.
  • All keys are namespaced under "postback:rl:" so they never clash with
    other apps using the same cache.

Usage:
    from .utils.rate_limiter import PostbackRateLimiter

    limiter = PostbackRateLimiter()
    if not limiter.is_allowed(network_key="cpalead", source_ip="1.2.3.4"):
        raise RateLimitExceededException()
"""
import logging
import time

from django.core.cache import cache

from ..constants import (
    POSTBACK_RATE_LIMIT_BURST,
    POSTBACK_RATE_LIMIT_PER_NETWORK,
)

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "postback:rl"
_MINUTE_WINDOW = 60       # seconds
_SECOND_WINDOW = 1        # seconds


def _parse_rate(rate_str: str) -> int:
    """
    Parse a rate string like '1000/minute' or '50/second' into a count.
    Returns the numeric limit.
    """
    try:
        count, _ = rate_str.split("/")
        return int(count.strip())
    except Exception:
        return 1000


class PostbackRateLimiter:
    """
    Sliding-window rate limiter backed by Django cache.

    Two windows checked per request:
    1. Per-minute window (per network_key)
    2. Per-second burst window (per network_key + source_ip)
    """

    def __init__(self):
        self.per_minute_limit = _parse_rate(POSTBACK_RATE_LIMIT_PER_NETWORK)
        self.burst_limit = _parse_rate(POSTBACK_RATE_LIMIT_BURST)

    def is_allowed(self, network_key: str, source_ip: str = "") -> bool:
        """
        Check if the request is within rate limits.
        Returns True if allowed, False if rate-limited.
        Does NOT raise – caller decides how to handle False.
        """
        try:
            minute_ok = self._check_window(
                key=self._minute_key(network_key),
                limit=self.per_minute_limit,
                window=_MINUTE_WINDOW,
            )
            if not minute_ok:
                logger.warning(
                    "Postback rate limit exceeded: network=%r per_minute_limit=%d",
                    network_key, self.per_minute_limit,
                )
                return False

            if source_ip:
                burst_ok = self._check_window(
                    key=self._burst_key(network_key, source_ip),
                    limit=self.burst_limit,
                    window=_SECOND_WINDOW,
                )
                if not burst_ok:
                    logger.warning(
                        "Postback burst rate limit exceeded: network=%r ip=%r burst_limit=%d",
                        network_key, source_ip, self.burst_limit,
                    )
                    return False

            return True

        except Exception as exc:
            # Cache failures should NOT block postbacks – fail open
            logger.error("PostbackRateLimiter cache error (failing open): %s", exc)
            return True

    def get_remaining(self, network_key: str) -> int:
        """
        Return remaining requests allowed in the current minute window.
        Returns per_minute_limit if cache key doesn't exist yet.
        """
        try:
            current = cache.get(self._minute_key(network_key), 0)
            return max(0, self.per_minute_limit - current)
        except Exception:
            return self.per_minute_limit

    def _check_window(self, key: str, limit: int, window: int) -> bool:
        """
        Increment the counter for the window, return True if still within limit.
        Uses cache.add() for atomic set-if-not-exists, then incr().
        """
        # Try to add the key (only succeeds if it doesn't exist)
        added = cache.add(key, 1, timeout=window)
        if added:
            return True  # First request in this window

        # Key already exists – increment
        try:
            count = cache.incr(key)
        except ValueError:
            # Key disappeared between add check and incr (race) – allow
            cache.set(key, 1, timeout=window)
            return True

        return count <= limit

    def _minute_key(self, network_key: str) -> str:
        # Bucket by minute so windows reset cleanly
        minute_bucket = int(time.time()) // _MINUTE_WINDOW
        return f"{_CACHE_PREFIX}:min:{network_key}:{minute_bucket}"

    def _burst_key(self, network_key: str, source_ip: str) -> str:
        second_bucket = int(time.time()) // _SECOND_WINDOW
        # Hash IP to avoid storing PII in cache keys directly
        import hashlib
        ip_hash = hashlib.md5(source_ip.encode()).hexdigest()[:8]
        return f"{_CACHE_PREFIX}:burst:{network_key}:{ip_hash}:{second_bucket}"


# Module-level singleton – instantiated once, reused across requests
_limiter = PostbackRateLimiter()


def check_postback_rate_limit(network_key: str, source_ip: str = "") -> bool:
    """
    Module-level convenience function.
    Returns True if allowed, False if rate-limited.
    """
    return _limiter.is_allowed(network_key=network_key, source_ip=source_ip)


def get_postback_rate_limit_remaining(network_key: str) -> int:
    """Return remaining allowed requests in the current minute window."""
    return _limiter.get_remaining(network_key)

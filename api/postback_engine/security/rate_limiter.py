"""
security/rate_limiter.py
─────────────────────────
Token-bucket rate limiter for postback endpoints.
Uses Redis atomic operations for distributed rate limiting.
Protects against: DDoS, credential stuffing, API abuse.
"""
from __future__ import annotations
import logging
import time
from django.core.cache import cache
from ..exceptions import RateLimitExceededException

logger = logging.getLogger(__name__)

_KEY_PATTERN = "pe:rl:{scope}:{identifier}"


class RateLimiter:
    """
    Sliding window rate limiter.
    Can be applied per: network, IP, user, or API key.
    """

    def check_and_increment(
        self,
        identifier: str,
        scope: str = "global",
        limit: int = 1000,
        window_seconds: int = 60,
    ) -> None:
        """
        Check rate limit and increment counter.
        Raises RateLimitExceededException if limit exceeded.
        """
        key = _KEY_PATTERN.format(scope=scope, identifier=identifier)
        try:
            current = self._incr(key, window_seconds)
            if current > limit:
                retry_after = self._get_ttl(key)
                raise RateLimitExceededException(
                    f"Rate limit exceeded: {current}/{limit} requests in {window_seconds}s.",
                    retry_after=retry_after,
                )
        except RateLimitExceededException:
            raise
        except Exception as exc:
            # Redis failure → log and allow (fail open)
            logger.warning("RateLimiter Redis error (fail open): %s", exc)

    def get_remaining(self, identifier: str, scope: str = "global", limit: int = 1000) -> int:
        """Return remaining request count in current window."""
        key = _KEY_PATTERN.format(scope=scope, identifier=identifier)
        try:
            current = int(cache.get(key) or 0)
            return max(0, limit - current)
        except Exception:
            return limit

    def reset(self, identifier: str, scope: str = "global") -> None:
        """Manually reset rate limit counter."""
        key = _KEY_PATTERN.format(scope=scope, identifier=identifier)
        cache.delete(key)

    def check_network(self, network) -> None:
        """Check rate limit for a network."""
        limit = getattr(network, "rate_limit_per_minute", 1000)
        self.check_and_increment(
            identifier=str(network.id),
            scope="network",
            limit=limit,
            window_seconds=60,
        )

    def check_ip(self, ip: str, limit: int = 200) -> None:
        """Check rate limit for an IP address."""
        if not ip:
            return
        self.check_and_increment(
            identifier=ip,
            scope="ip",
            limit=limit,
            window_seconds=60,
        )

    @staticmethod
    def _incr(key: str, ttl: int) -> int:
        try:
            return cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=ttl)
            return cache.incr(key)

    @staticmethod
    def _get_ttl(key: str) -> int:
        try:
            client = cache.client.get_client()
            ttl = client.ttl(key)
            return max(0, ttl)
        except Exception:
            return 60


rate_limiter = RateLimiter()

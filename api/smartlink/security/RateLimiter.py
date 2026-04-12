"""
SmartLink Advanced Rate Limiter
Distributed rate limiting using Redis sliding window algorithm.
Far superior to Django's built-in throttling.

Supports:
- Per-IP rate limiting
- Per-publisher rate limiting
- Per-slug rate limiting (protect specific SmartLinks)
- Burst allowance
- Automatic ban for repeat offenders
"""
import time
import logging
import hashlib
from django.core.cache import cache

logger = logging.getLogger('smartlink.security.ratelimit')


class SlidingWindowRateLimiter:
    """
    Redis-based sliding window rate limiter.
    More accurate than fixed window — no "boundary burst" vulnerability.
    """

    def __init__(self, limit: int, window_seconds: int, ban_threshold: int = 0):
        self.limit           = limit
        self.window          = window_seconds
        self.ban_threshold   = ban_threshold  # auto-ban after N violations

    def is_allowed(self, identifier: str) -> tuple:
        """
        Check if request is allowed.
        Returns: (allowed: bool, current_count: int, retry_after: int)
        """
        now       = time.time()
        window_start = now - self.window
        key       = f'rl:{hashlib.md5(identifier.encode()).hexdigest()}'
        ban_key   = f'rl:ban:{hashlib.md5(identifier.encode()).hexdigest()}'

        # Check if banned
        if cache.get(ban_key):
            return False, self.limit + 1, self.window

        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')

            pipe = conn.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Count remaining
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiry
            pipe.expire(key, self.window + 1)
            results = pipe.execute()

            count = results[1]

            if count >= self.limit:
                # Track violations for auto-ban
                if self.ban_threshold > 0:
                    viol_key = f'rl:viol:{hashlib.md5(identifier.encode()).hexdigest()}'
                    violations = cache.get(viol_key, 0) + 1
                    cache.set(viol_key, violations, 3600)
                    if violations >= self.ban_threshold:
                        cache.set(ban_key, '1', 86400)
                        logger.warning(f"Auto-banned: {identifier[:50]} ({violations} violations)")

                retry_after = int(self.window - (now - window_start))
                return False, count, max(1, retry_after)

            return True, count, 0

        except Exception as e:
            logger.warning(f"Rate limiter Redis error: {e}")
            return True, 0, 0  # Fail open on Redis error

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests in current window."""
        now          = time.time()
        window_start = now - self.window
        key          = f'rl:{hashlib.md5(identifier.encode()).hexdigest()}'
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            conn.zremrangebyscore(key, 0, window_start)
            count = conn.zcard(key)
            return max(0, self.limit - count)
        except Exception:
            return self.limit


# ── Pre-configured rate limiters ───────────────────────────────────

# /go/<slug>/ — 1000 req/min per IP (burst-friendly)
REDIRECT_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=1000, window_seconds=60, ban_threshold=10
)

# /api/ — 200 req/min per publisher
API_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=200, window_seconds=60, ban_threshold=20
)

# /postback/ — 500 req/min per IP
POSTBACK_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=500, window_seconds=60
)

# Burst protection: 50 req/sec per IP on redirects
BURST_LIMITER = SlidingWindowRateLimiter(
    limit=50, window_seconds=1, ban_threshold=30
)

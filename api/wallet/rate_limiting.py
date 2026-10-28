# api/wallet/rate_limiting.py
"""
Advanced rate limiting — Redis-based sliding window algorithm.
More accurate than fixed window. Prevents burst abuse.

Features:
  - Sliding window counter (Redis sorted sets)
  - Per-user, per-IP, per-endpoint limits
  - Automatic retry-after headers
  - Whitelist for trusted IPs/users

Usage:
    limiter = SlidingWindowRateLimiter("withdrawal", limit=5, window=3600)
    allowed, remaining = limiter.check(user_id=request.user.id)
"""
import logging
import time
from typing import Tuple
from django.core.cache import cache

logger = logging.getLogger("wallet.rate_limiting")

LIMITS = {
    "withdrawal":      {"limit": 5,   "window": 3600},
    "earning_record":  {"limit": 100, "window": 3600},
    "kyc_submit":      {"limit": 3,   "window": 86400},
    "transfer":        {"limit": 10,  "window": 3600},
    "payment_method":  {"limit": 5,   "window": 3600},
    "offer_convert":   {"limit": 50,  "window": 3600},
    "admin_op":        {"limit": 100, "window": 3600},
    "webhook":         {"limit": 500, "window": 60},
    "api_global":      {"limit": 300, "window": 60},
    "login_attempt":   {"limit": 10,  "window": 900},
}

WHITELIST_IPS  = set(getattr(__import__("django.conf",fromlist=["settings"]).settings,
                              "RATE_LIMIT_WHITELIST_IPS", []))
WHITELIST_USERS= set(getattr(__import__("django.conf",fromlist=["settings"]).settings,
                              "RATE_LIMIT_WHITELIST_USERS", []))


class SlidingWindowRateLimiter:
    """Redis sorted-set sliding window rate limiter."""

    def __init__(self, action: str, limit: int = None, window: int = None):
        cfg         = LIMITS.get(action, {"limit": 100, "window": 60})
        self.action = action
        self.limit  = limit or cfg["limit"]
        self.window = window or cfg["window"]

    def check(self, user_id: int = 0, ip_address: str = "") -> Tuple[bool, int]:
        """Check rate limit. Returns (allowed, remaining)."""
        if ip_address in WHITELIST_IPS or user_id in WHITELIST_USERS:
            return True, self.limit

        key = f"rl:{self.action}:{user_id or ip_address}"
        now = time.time()

        try:
            pipe = cache.client.get_client().pipeline()
            pipe.zremrangebyscore(key, 0, now - self.window)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window)
            _, current, _, _ = pipe.execute()
            remaining = max(0, self.limit - current - 1)
            if current >= self.limit:
                logger.warning(f"Rate limit: action={self.action} user={user_id} ip={ip_address}")
                return False, 0
            return True, remaining
        except Exception:
            # Fallback to simple counter
            return self._simple_check(key)

    def _simple_check(self, key: str) -> Tuple[bool, int]:
        count = cache.get(key, 0)
        if count >= self.limit:
            return False, 0
        try:
            cache.incr(key)
        except Exception:
            cache.set(key, 1, self.window)
        return True, max(0, self.limit - count - 1)

    def reset(self, user_id: int = 0, ip_address: str = ""):
        key = f"rl:{self.action}:{user_id or ip_address}"
        cache.delete(key)


def check_rate_limit(action: str, user_id: int = 0, ip_address: str = "") -> Tuple[bool, int]:
    """Convenience function for one-off rate limit checks."""
    limiter = SlidingWindowRateLimiter(action)
    return limiter.check(user_id=user_id, ip_address=ip_address)

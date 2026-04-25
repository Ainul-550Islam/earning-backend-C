# api/wallet/rate_limiter.py
"""
Wallet-specific rate limiting.
Uses Redis cache with atomic increment for thread-safe counters.

Limits:
  - Withdrawal: 5 per hour per user
  - Earning API: 100 per hour per user
  - KYC submit: 3 per day per user
  - Transfer: 10 per hour per user
  - Admin ops: 50 per hour per admin
"""
import logging
from functools import wraps
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response

logger = logging.getLogger("wallet.rate_limiter")

# Rate limit configuration
RATE_LIMITS = {
    "withdrawal":       {"limit": 5,   "window": 3600},   # 5/hour
    "earning_record":   {"limit": 100, "window": 3600},   # 100/hour
    "kyc_submit":       {"limit": 3,   "window": 86400},  # 3/day
    "transfer":         {"limit": 10,  "window": 3600},   # 10/hour
    "payment_method":   {"limit": 5,   "window": 3600},   # 5/hour
    "offer_convert":    {"limit": 50,  "window": 3600},   # 50/hour
    "admin_credit":     {"limit": 50,  "window": 3600},   # 50/hour (admin)
    "webhook_receive":  {"limit": 500, "window": 60},     # 500/min (gateway)
    "api_global":       {"limit": 200, "window": 60},     # 200/min global
}


class WalletRateLimiter:
    """Redis-based rate limiter for wallet operations."""

    @staticmethod
    def check(user_id: int, action: str, ip_address: str = "") -> tuple:
        """
        Check if user has exceeded rate limit for action.
        Returns: (allowed: bool, remaining: int, reset_at: int)
        """
        config = RATE_LIMITS.get(action, {"limit": 100, "window": 3600})
        limit  = config["limit"]
        window = config["window"]

        # Key: per-user + per-action
        key = f"ratelimit:{action}:user:{user_id}"

        try:
            current = cache.get(key, 0)
            if current >= limit:
                ttl = cache.ttl(key) if hasattr(cache, "ttl") else window
                logger.warning(f"Rate limit hit: user={user_id} action={action} count={current}")
                return False, 0, int(timezone.now().timestamp()) + (ttl or window)

            # Increment with expiry
            pipe = None
            try:
                # Redis atomic increment
                new_count = cache.incr(key)
                if new_count == 1:
                    cache.expire(key, window)
                remaining = limit - new_count
                return True, max(remaining, 0), 0
            except AttributeError:
                # Non-Redis cache: simple get/set
                new_count = (cache.get(key) or 0) + 1
                cache.set(key, new_count, window)
                return True, max(limit - new_count, 0), 0

        except Exception as e:
            logger.debug(f"Rate limiter error: {e}")
            return True, limit, 0  # Fail open

    @staticmethod
    def reset(user_id: int, action: str):
        """Reset rate limit for a user/action (admin use)."""
        key = f"ratelimit:{action}:user:{user_id}"
        cache.delete(key)

    @staticmethod
    def get_status(user_id: int, action: str) -> dict:
        """Get current rate limit status."""
        config = RATE_LIMITS.get(action, {"limit": 100, "window": 3600})
        key    = f"ratelimit:{action}:user:{user_id}"
        current = cache.get(key, 0)
        return {
            "action":    action,
            "limit":     config["limit"],
            "used":      current,
            "remaining": max(config["limit"] - current, 0),
            "window":    config["window"],
        }


def rate_limit(action: str):
    """
    Decorator for DRF viewset actions.
    Usage:
        @rate_limit("withdrawal")
        def create(self, request, *args, **kwargs):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            user_id = request.user.id if request.user.is_authenticated else 0
            ip      = request.META.get("REMOTE_ADDR", "")

            allowed, remaining, reset_at = WalletRateLimiter.check(user_id, action, ip)

            if not allowed:
                return Response({
                    "success":   False,
                    "error":     f"Rate limit exceeded for {action}. Try again later.",
                    "remaining": 0,
                    "reset_at":  reset_at,
                }, status=429, headers={
                    "X-RateLimit-Limit":     str(RATE_LIMITS.get(action, {}).get("limit", 100)),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After":           str(reset_at),
                })

            response = func(self, request, *args, **kwargs)
            if hasattr(response, "headers"):
                response["X-RateLimit-Remaining"] = str(remaining)
            return response
        return wrapper
    return decorator

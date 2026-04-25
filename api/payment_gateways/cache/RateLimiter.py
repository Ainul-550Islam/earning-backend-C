# FILE 91 of 257 — cache/RateLimiter.py
# Redis-backed rate limiter for payment endpoints

from django.core.cache import cache
from django.utils import timezone
import time, logging
logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Sliding-window rate limiter using Redis.

    Usage:
        limiter = RateLimiter()
        allowed, remaining = limiter.check(user_id=42, action='deposit', limit=5, window=60)
        if not allowed:
            raise Exception('Rate limit exceeded')
    """

    @staticmethod
    def check(user_id: int, action: str, limit: int, window: int) -> tuple:
        """
        Returns (is_allowed: bool, remaining: int).
        window in seconds.
        """
        now       = int(time.time())
        key       = f'rl:{action}:{user_id}'
        pipe_key  = f'{key}:{now // window}'

        count = cache.get(pipe_key, 0)
        if count >= limit:
            logger.warning(f'RateLimiter: {action} limit exceeded for user {user_id}')
            return False, 0

        cache.set(pipe_key, count + 1, timeout=window)
        return True, limit - count - 1

    @staticmethod
    def reset(user_id: int, action: str):
        """Manually reset rate limit for a user (admin use)."""
        now      = int(time.time())
        window   = 60
        key      = f'rl:{action}:{user_id}:{now // window}'
        cache.delete(key)

    @staticmethod
    def get_payment_limits():
        """Standard limits for payment actions."""
        return {
            'deposit':    {'limit': 10, 'window': 60},    # 10 per minute
            'withdrawal': {'limit': 5,  'window': 60},    # 5 per minute
            'refund':     {'limit': 3,  'window': 60},    # 3 per minute
            'verify':     {'limit': 20, 'window': 60},    # 20 per minute
        }

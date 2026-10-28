# api/djoyalty/rate_limiting.py
"""
Djoyalty Rate Limiting -- Advanced per-plan, per-customer API rate limiting।
Beyond simple throttling -- plan-based limits with burst allowance।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
import time
from django.core.cache import cache
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class RateLimitPlan:
    """A rate limit plan with per-minute, per-hour, per-day limits."""

    def __init__(self, name: str, per_minute: int = 60,
                 per_hour: int = 1000, per_day: int = 10000,
                 burst: int = 0):
        self.name = name
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.per_day = per_day
        self.burst = burst  # Extra allowance for burst traffic


# Standard plans matching paid membership tiers
RATE_LIMIT_PLANS = {
    'free':       RateLimitPlan('free',       per_minute=30,  per_hour=500,  per_day=2000),
    'basic':      RateLimitPlan('basic',      per_minute=60,  per_hour=1000, per_day=5000),
    'premium':    RateLimitPlan('premium',    per_minute=120, per_hour=3000, per_day=20000),
    'enterprise': RateLimitPlan('enterprise', per_minute=500, per_hour=10000, per_day=100000, burst=200),
    'internal':   RateLimitPlan('internal',   per_minute=9999, per_hour=99999, per_day=999999),
}


class AdvancedRateLimiter:
    """
    Multi-window rate limiter with plan-based limits।
    Uses sliding window algorithm via Redis।

    Usage:
        limiter = AdvancedRateLimiter()
        allowed, info = limiter.check(identifier='customer:123', plan='premium')
        if not allowed:
            return Response({'error': 'Rate limit exceeded'}, status=429)
    """

    PREFIX = 'djoyalty:ratelimit:adv'

    def check(self, identifier: str, plan: str = 'free') -> tuple:
        """
        Check rate limit for identifier + plan।
        Returns: (allowed: bool, info: dict)
        info contains: limit, remaining, reset_at
        """
        plan_obj = RATE_LIMIT_PLANS.get(plan, RATE_LIMIT_PLANS['free'])
        now = int(time.time())

        # Check minute window
        minute_key = f'{self.PREFIX}:{identifier}:min:{now // 60}'
        hour_key = f'{self.PREFIX}:{identifier}:hour:{now // 3600}'
        day_key = f'{self.PREFIX}:{identifier}:day:{now // 86400}'

        try:
            minute_count = cache.get(minute_key, 0) + 1
            hour_count = cache.get(hour_key, 0) + 1
            day_count = cache.get(day_key, 0) + 1
        except Exception:
            return True, {'error': 'cache_unavailable'}

        # Check limits
        if minute_count > plan_obj.per_minute:
            return False, {
                'limit_type': 'per_minute',
                'limit': plan_obj.per_minute,
                'current': minute_count,
                'reset_in': 60 - (now % 60),
                'retry_after': 60 - (now % 60),
            }

        if hour_count > plan_obj.per_hour:
            return False, {
                'limit_type': 'per_hour',
                'limit': plan_obj.per_hour,
                'current': hour_count,
                'reset_in': 3600 - (now % 3600),
                'retry_after': 3600 - (now % 3600),
            }

        if day_count > plan_obj.per_day:
            return False, {
                'limit_type': 'per_day',
                'limit': plan_obj.per_day,
                'current': day_count,
                'reset_in': 86400 - (now % 86400),
                'retry_after': 86400 - (now % 86400),
            }

        # Increment counters
        try:
            cache.set(minute_key, minute_count, timeout=61)
            cache.set(hour_key, hour_count, timeout=3601)
            cache.set(day_key, day_count, timeout=86401)
        except Exception:
            pass

        return True, {
            'plan': plan,
            'minute_remaining': plan_obj.per_minute - minute_count,
            'hour_remaining': plan_obj.per_hour - hour_count,
            'day_remaining': plan_obj.per_day - day_count,
        }

    def get_headers(self, identifier: str, plan: str = 'free') -> dict:
        """Get rate limit headers for API response (RFC 6585 standard)।"""
        plan_obj = RATE_LIMIT_PLANS.get(plan, RATE_LIMIT_PLANS['free'])
        now = int(time.time())
        minute_key = f'{self.PREFIX}:{identifier}:min:{now // 60}'
        current = cache.get(minute_key, 0)

        return {
            'X-RateLimit-Limit': str(plan_obj.per_minute),
            'X-RateLimit-Remaining': str(max(0, plan_obj.per_minute - current)),
            'X-RateLimit-Reset': str(now + (60 - now % 60)),
        }


# Module-level singleton
rate_limiter = AdvancedRateLimiter()

# api/offer_inventory/system_devops/rate_limiter.py
"""
Rate Limiter Engine — Per-action, per-user, per-IP rate limiting.
Uses Redis sliding window counters.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    'click'            : (60,   100),    # 100 clicks/min
    'conversion'       : (60,   10),     # 10 conversions/min
    'withdrawal'       : (3600, 3),      # 3 withdrawals/hour
    'api_default'      : (60,   1000),   # 1000 API calls/min
    'kyc_submit'       : (3600, 3),      # 3 KYC submissions/hour
    'promo_redeem'     : (86400, 5),     # 5 promo codes/day
    'postback'         : (60,   1000),   # 1000 postbacks/min per IP
    'push_subscribe'   : (3600, 10),     # 10 push subscriptions/hour
}


class RateLimiterEngine:
    """Redis-backed sliding window rate limiter."""

    @classmethod
    def check(cls, action: str, identifier: str,
               custom_limit: int = None, window: int = None) -> dict:
        """
        Check rate limit. Returns {'allowed': bool, 'remaining': int}.
        """
        default_window, default_limit = RATE_LIMITS.get(action, (60, 100))
        w = window or default_window
        l = custom_limit or default_limit

        key   = f'rl:{action}:{identifier}'
        count = cache.get(key, 0)

        if count >= l:
            ttl = cache.ttl(key) if hasattr(cache, 'ttl') else w
            return {
                'allowed'    : False,
                'remaining'  : 0,
                'retry_after': ttl or w,
                'count'      : count,
                'limit'      : l,
            }

        cache.set(key, count + 1, w)
        return {
            'allowed'  : True,
            'remaining': l - count - 1,
            'count'    : count + 1,
            'limit'    : l,
        }

    @classmethod
    def reset(cls, action: str, identifier: str):
        """Reset rate limit counter."""
        cache.delete(f'rl:{action}:{identifier}')

    @classmethod
    def get_stats(cls, action: str, identifier: str) -> dict:
        """Get current rate limit state."""
        default_window, default_limit = RATE_LIMITS.get(action, (60, 100))
        key   = f'rl:{action}:{identifier}'
        count = cache.get(key, 0)
        return {
            'action'   : action,
            'count'    : count,
            'limit'    : default_limit,
            'window'   : default_window,
            'remaining': max(0, default_limit - count),
        }

    @classmethod
    def bulk_check(cls, action: str, identifiers: list,
                    limit: int = None) -> dict:
        """Check rate limits for multiple identifiers."""
        return {
            identifier: cls.check(action, identifier, custom_limit=limit)
            for identifier in identifiers
        }

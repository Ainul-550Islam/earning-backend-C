# kyc/security/rate_limiter.py  ── WORLD #1
"""KYC-specific rate limiting beyond DRF throttles"""
import logging
from ..utils.cache_utils import cache_get, cache_set

logger = logging.getLogger(__name__)


class KYCRateLimiter:
    """
    Redis-backed rate limiter for KYC operations.
    Usage:
        limiter = KYCRateLimiter(user_id=user.id)
        if not limiter.allow('submit', limit=5, window=3600):
            raise KYCRateLimitException()
    """

    def __init__(self, user_id: int, tenant_id: int = None):
        self.user_id   = user_id
        self.tenant_id = tenant_id

    def _key(self, action: str) -> str:
        base = f"kyc:rl:{action}:{self.user_id}"
        if self.tenant_id:
            base += f":{self.tenant_id}"
        return base

    def allow(self, action: str, limit: int, window: int) -> bool:
        """
        Returns True if request is allowed.
        limit: max requests
        window: seconds
        """
        key     = self._key(action)
        current = cache_get(key, 0)

        if current >= limit:
            logger.warning(f"Rate limit hit: user={self.user_id} action={action} count={current}")
            return False

        new_val = current + 1
        # First hit → set with TTL, subsequent → just increment
        if current == 0:
            cache_set(key, new_val, ttl=window)
        else:
            try:
                from django.core.cache import cache
                cache.incr(key)
            except Exception:
                cache_set(key, new_val, ttl=window)

        return True

    def reset(self, action: str):
        from ..utils.cache_utils import cache_delete
        cache_delete(self._key(action))

    def remaining(self, action: str, limit: int) -> int:
        current = cache_get(self._key(action), 0)
        return max(0, limit - current)


def check_submission_rate_limit(user_id: int) -> bool:
    """Quick check — 5 submits per hour."""
    limiter = KYCRateLimiter(user_id=user_id)
    return limiter.allow('submit', limit=5, window=3600)


def check_fraud_check_rate_limit(user_id: int) -> bool:
    """10 fraud-checks per hour."""
    limiter = KYCRateLimiter(user_id=user_id)
    return limiter.allow('fraud_check', limit=10, window=3600)

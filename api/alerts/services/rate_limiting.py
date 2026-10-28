# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)


class RateLimitingService:
    """
    Consolidates rate limiting logic.
    Eliminates duplicates from: rate_limiter.py + utils.py
    """

    # Rate limit configurations
    LIMITS = {
        'anonymous': {'requests': 100, 'period': 3600},  # 100 per hour
        'authenticated': {'requests': 1000, 'period': 3600},  # 1000 per hour
        'premium': {'requests': 10000, 'period': 3600},  # 10000 per hour
        'expensive_op': {'requests': 10, 'period': 3600},  # 10 per hour for expensive ops
    }

    @staticmethod
    def rate_limit(identifier, limit_type='authenticated'):
        """
        Check if request is within rate limits.
        
        Previously duplicated in:
        - alerts/rate_limiter.py
        - alerts/utils.py
        
        Args:
            identifier: User ID or IP address
            limit_type: Type of limit to apply
            
        Returns:
            dict: {'allowed': bool, 'remaining': int, 'reset_at': datetime}
        """
        logger.info(f"Checking rate limit for {identifier}")
        
        if limit_type not in RateLimitingService.LIMITS:
            logger.warning(f"Unknown limit type: {limit_type}")
            limit_type = 'authenticated'
        
        limit_config = RateLimitingService.LIMITS[limit_type]
        cache_key = f"ratelimit_{identifier}_{limit_type}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        allowed = current_count < limit_config['requests']
        
        if allowed:
            # Increment counter
            cache.set(cache_key, current_count + 1, limit_config['period'])
            remaining = limit_config['requests'] - (current_count + 1)
        else:
            remaining = 0
        
        # Calculate reset time (cache.ttl() is Redis-specific; not all cache
        # backends implement it, so fall back to the configured period)
        ttl_func = getattr(cache, 'ttl', None)
        ttl = ttl_func(cache_key) if callable(ttl_func) else None
        
        result = {
            'allowed': allowed,
            'remaining': remaining,
            'limit': limit_config['requests'],
            'reset_seconds': ttl if ttl else limit_config['period']
        }
        
        logger.info(f"Rate limit result: {result}")
        
        return result

    @staticmethod
    def reset_rate_limit(identifier, limit_type='authenticated'):
        """Reset rate limit for an identifier"""
        cache_key = f"ratelimit_{identifier}_{limit_type}"
        cache.delete(cache_key)
        logger.info(f"Reset rate limit for {identifier}")

    @staticmethod
    def is_rate_limited(identifier, limit_type='authenticated'):
        """Check if identifier is rate limited"""
        result = RateLimitingService.rate_limit(identifier, limit_type)
        return not result['allowed']

    @staticmethod
    def get_rate_limit_status(identifier):
        """Get rate limit status for all limit types"""
        status = {}
        
        for limit_type in RateLimitingService.LIMITS:
            status[limit_type] = RateLimitingService.rate_limit(identifier, limit_type)
        
        return status


__all__ = ['RateLimitingService']

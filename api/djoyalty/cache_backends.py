# api/djoyalty/cache_backends.py
"""
Cache key management and caching utilities for Djoyalty।
Django cache framework ব্যবহার করে (Redis recommended)।
"""
import logging
from functools import wraps
from typing import Any, Optional, Callable
from django.core.cache import cache
from .constants import (
    CACHE_TTL_CUSTOMER_BALANCE, CACHE_TTL_TIER_INFO,
    CACHE_TTL_LEADERBOARD, CACHE_TTL_EARN_RULES, CACHE_TTL_CAMPAIGN_ACTIVE,
)

logger = logging.getLogger('djoyalty.cache')

# ==================== CACHE KEY BUILDERS ====================

def customer_balance_key(customer_id: int, tenant_id: int = None) -> str:
    return f'djoyalty:balance:{tenant_id or 0}:{customer_id}'

def customer_tier_key(customer_id: int, tenant_id: int = None) -> str:
    return f'djoyalty:tier:{tenant_id or 0}:{customer_id}'

def leaderboard_key(tenant_id: int = None, period: str = 'all', limit: int = 10) -> str:
    return f'djoyalty:leaderboard:{tenant_id or 0}:{period}:{limit}'

def earn_rules_key(tenant_id: int = None, trigger: str = 'purchase') -> str:
    return f'djoyalty:earn_rules:{tenant_id or 0}:{trigger}'

def active_campaigns_key(tenant_id: int = None) -> str:
    return f'djoyalty:campaigns:active:{tenant_id or 0}'

def voucher_key(code: str) -> str:
    return f'djoyalty:voucher:{code}'

def customer_stats_key(customer_id: int) -> str:
    return f'djoyalty:stats:{customer_id}'


# ==================== CACHE OPERATIONS ====================

class DjoyaltyCache:
    """Unified cache interface for Djoyalty।"""

    @staticmethod
    def get_balance(customer_id: int, tenant_id: int = None) -> Optional[Any]:
        key = customer_balance_key(customer_id, tenant_id)
        return cache.get(key)

    @staticmethod
    def set_balance(customer_id: int, balance, tenant_id: int = None) -> None:
        key = customer_balance_key(customer_id, tenant_id)
        cache.set(key, balance, timeout=CACHE_TTL_CUSTOMER_BALANCE)

    @staticmethod
    def invalidate_balance(customer_id: int, tenant_id: int = None) -> None:
        key = customer_balance_key(customer_id, tenant_id)
        cache.delete(key)
        logger.debug('Invalidated balance cache for customer %d', customer_id)

    @staticmethod
    def get_tier(customer_id: int, tenant_id: int = None) -> Optional[Any]:
        key = customer_tier_key(customer_id, tenant_id)
        return cache.get(key)

    @staticmethod
    def set_tier(customer_id: int, tier_name: str, tenant_id: int = None) -> None:
        key = customer_tier_key(customer_id, tenant_id)
        cache.set(key, tier_name, timeout=CACHE_TTL_TIER_INFO)

    @staticmethod
    def invalidate_tier(customer_id: int, tenant_id: int = None) -> None:
        cache.delete(customer_tier_key(customer_id, tenant_id))

    @staticmethod
    def get_leaderboard(tenant_id: int = None, period: str = 'all', limit: int = 10) -> Optional[list]:
        key = leaderboard_key(tenant_id, period, limit)
        return cache.get(key)

    @staticmethod
    def set_leaderboard(data: list, tenant_id: int = None, period: str = 'all', limit: int = 10) -> None:
        key = leaderboard_key(tenant_id, period, limit)
        cache.set(key, data, timeout=CACHE_TTL_LEADERBOARD)

    @staticmethod
    def get_earn_rules(tenant_id: int = None, trigger: str = 'purchase') -> Optional[list]:
        key = earn_rules_key(tenant_id, trigger)
        return cache.get(key)

    @staticmethod
    def set_earn_rules(rules: list, tenant_id: int = None, trigger: str = 'purchase') -> None:
        key = earn_rules_key(tenant_id, trigger)
        cache.set(key, rules, timeout=CACHE_TTL_EARN_RULES)

    @staticmethod
    def invalidate_earn_rules(tenant_id: int = None) -> None:
        """সব trigger এর earn rules invalidate করো।"""
        from .choices import EARN_RULE_TRIGGER_CHOICES
        for trigger, _ in EARN_RULE_TRIGGER_CHOICES:
            cache.delete(earn_rules_key(tenant_id, trigger))

    @staticmethod
    def get_active_campaigns(tenant_id: int = None) -> Optional[list]:
        key = active_campaigns_key(tenant_id)
        return cache.get(key)

    @staticmethod
    def set_active_campaigns(campaigns: list, tenant_id: int = None) -> None:
        key = active_campaigns_key(tenant_id)
        cache.set(key, campaigns, timeout=CACHE_TTL_CAMPAIGN_ACTIVE)

    @staticmethod
    def invalidate_campaigns(tenant_id: int = None) -> None:
        cache.delete(active_campaigns_key(tenant_id))

    @staticmethod
    def flush_customer_cache(customer_id: int, tenant_id: int = None) -> None:
        """Customer এর সব cache entries flush করো।"""
        DjoyaltyCache.invalidate_balance(customer_id, tenant_id)
        DjoyaltyCache.invalidate_tier(customer_id, tenant_id)
        logger.info('Flushed all cache for customer %d', customer_id)

    @staticmethod
    def flush_tenant_cache(tenant_id: int) -> None:
        """Tenant এর সব cache flush করো।"""
        DjoyaltyCache.invalidate_earn_rules(tenant_id)
        DjoyaltyCache.invalidate_campaigns(tenant_id)
        cache.delete(leaderboard_key(tenant_id))
        logger.info('Flushed all cache for tenant %d', tenant_id)


# ==================== CACHE DECORATOR ====================

def djoyalty_cached(key_func: Callable, timeout: int = 300):
    """
    Function result cache করার decorator।
    Usage:
        @djoyalty_cached(key_func=lambda customer_id: f'balance:{customer_id}', timeout=300)
        def get_balance(customer_id): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_func(*args, **kwargs)
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator

# api/djoyalty/caching.py
"""
Djoyalty Caching -- Redis-backed caching layer for loyalty data।
Points balance, tier info, customer profile -- all cached।
"Do not summarize or skip any logic. Provide the full code."
"""
import json
import logging
from decimal import Decimal
from functools import wraps
from typing import Any, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache TTLs (seconds)
TTL_BALANCE         = 30        # Points balance -- short TTL (changes often)
TTL_TIER            = 300       # Tier info -- 5 min
TTL_CUSTOMER        = 60        # Customer profile -- 1 min
TTL_EARN_RULES      = 600       # Earn rules -- 10 min (rarely changes)
TTL_CATALOG         = 300       # Reward catalog -- 5 min
TTL_FEATURE_FLAGS   = 60        # Feature flags -- 1 min
TTL_HEALTH_CHECK    = 60        # Health check result -- 1 min
TTL_ANALYTICS       = 3600      # Analytics/reports -- 1 hour


class LoyaltyCache:
    """
    Centralized cache manager for all loyalty data।
    Uses Django cache backend (Redis in production)।

    Keys are prefixed with 'djoyalty:' for namespace isolation।
    """

    PREFIX = 'djoyalty'

    # ─── Points Balance ───────────────────────────────────────────

    @classmethod
    def get_balance(cls, customer_id: int) -> Optional[Decimal]:
        key = f'{cls.PREFIX}:balance:{customer_id}'
        val = cache.get(key)
        return Decimal(str(val)) if val is not None else None

    @classmethod
    def set_balance(cls, customer_id: int, balance: Decimal):
        key = f'{cls.PREFIX}:balance:{customer_id}'
        cache.set(key, str(balance), timeout=TTL_BALANCE)

    @classmethod
    def invalidate_balance(cls, customer_id: int):
        cache.delete(f'{cls.PREFIX}:balance:{customer_id}')

    # ─── Tier ─────────────────────────────────────────────────────

    @classmethod
    def get_tier(cls, customer_id: int) -> Optional[dict]:
        key = f'{cls.PREFIX}:tier:{customer_id}'
        return cache.get(key)

    @classmethod
    def set_tier(cls, customer_id: int, tier_data: dict):
        key = f'{cls.PREFIX}:tier:{customer_id}'
        cache.set(key, tier_data, timeout=TTL_TIER)

    @classmethod
    def invalidate_tier(cls, customer_id: int):
        cache.delete(f'{cls.PREFIX}:tier:{customer_id}')

    # ─── Customer Profile ─────────────────────────────────────────

    @classmethod
    def get_customer(cls, customer_id: int) -> Optional[dict]:
        key = f'{cls.PREFIX}:customer:{customer_id}'
        return cache.get(key)

    @classmethod
    def set_customer(cls, customer_id: int, data: dict):
        key = f'{cls.PREFIX}:customer:{customer_id}'
        cache.set(key, data, timeout=TTL_CUSTOMER)

    @classmethod
    def invalidate_customer(cls, customer_id: int):
        cache.delete(f'{cls.PREFIX}:customer:{customer_id}')

    # ─── Earn Rules ───────────────────────────────────────────────

    @classmethod
    def get_earn_rules(cls, tenant_id=None) -> Optional[list]:
        key = f'{cls.PREFIX}:earn_rules:{tenant_id or "default"}'
        return cache.get(key)

    @classmethod
    def set_earn_rules(cls, rules: list, tenant_id=None):
        key = f'{cls.PREFIX}:earn_rules:{tenant_id or "default"}'
        cache.set(key, rules, timeout=TTL_EARN_RULES)

    @classmethod
    def invalidate_earn_rules(cls, tenant_id=None):
        cache.delete(f'{cls.PREFIX}:earn_rules:{tenant_id or "default"}')

    # ─── Catalog ──────────────────────────────────────────────────

    @classmethod
    def get_catalog(cls, tenant_id=None, reward_type: str = '') -> Optional[list]:
        key = f'{cls.PREFIX}:catalog:{tenant_id or "default"}:{reward_type}'
        return cache.get(key)

    @classmethod
    def set_catalog(cls, items: list, tenant_id=None, reward_type: str = ''):
        key = f'{cls.PREFIX}:catalog:{tenant_id or "default"}:{reward_type}'
        cache.set(key, items, timeout=TTL_CATALOG)

    # ─── Session Lock (checkout) ──────────────────────────────────

    @classmethod
    def acquire_checkout_lock(cls, customer_id: int, timeout: int = 30) -> bool:
        """
        Acquire checkout session lock (Voucherify session lock pattern)।
        Prevents double-spending during checkout।
        Returns True if lock acquired, False if already locked।
        """
        key = f'{cls.PREFIX}:checkout_lock:{customer_id}'
        return cache.add(key, '1', timeout=timeout)

    @classmethod
    def release_checkout_lock(cls, customer_id: int):
        cache.delete(f'{cls.PREFIX}:checkout_lock:{customer_id}')

    @classmethod
    def is_checkout_locked(cls, customer_id: int) -> bool:
        return cache.get(f'{cls.PREFIX}:checkout_lock:{customer_id}') is not None

    # ─── Unread Notification Count ────────────────────────────────

    @classmethod
    def get_unread_count(cls, customer_id: int) -> Optional[int]:
        val = cache.get(f'{cls.PREFIX}:unread:{customer_id}')
        return int(val) if val is not None else None

    @classmethod
    def set_unread_count(cls, customer_id: int, count: int):
        cache.set(f'{cls.PREFIX}:unread:{customer_id}', count, timeout=30)

    @classmethod
    def invalidate_unread_count(cls, customer_id: int):
        cache.delete(f'{cls.PREFIX}:unread:{customer_id}')

    # ─── Bulk Invalidation ────────────────────────────────────────

    @classmethod
    def invalidate_all_for_customer(cls, customer_id: int):
        """Invalidate all cached data for a customer।"""
        keys = [
            f'{cls.PREFIX}:balance:{customer_id}',
            f'{cls.PREFIX}:tier:{customer_id}',
            f'{cls.PREFIX}:customer:{customer_id}',
            f'{cls.PREFIX}:unread:{customer_id}',
            f'{cls.PREFIX}:checkout_lock:{customer_id}',
        ]
        cache.delete_many(keys)

    # ─── Generic ─────────────────────────────────────────────────

    @classmethod
    def get(cls, key: str, default=None):
        return cache.get(f'{cls.PREFIX}:{key}', default)

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300):
        cache.set(f'{cls.PREFIX}:{key}', value, timeout=ttl)

    @classmethod
    def delete(cls, key: str):
        cache.delete(f'{cls.PREFIX}:{key}')


def cached_loyalty(key_fn, ttl: int = 300):
    """
    Decorator: cache function result in loyalty cache।
    key_fn: function(*args, **kwargs) -> cache key string

    Usage:
        @cached_loyalty(lambda customer_id: f'summary:{customer_id}', ttl=60)
        def get_customer_summary(customer_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            cached = LoyaltyCache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            if result is not None:
                LoyaltyCache.set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

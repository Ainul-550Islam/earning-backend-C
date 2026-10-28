# api/djoyalty/cache_backends.py
"""
Djoyalty -- cache backend।
Tier, balance, campaign cache management।
"""
import logging
from .constants import CACHE_TTL_TIER, CACHE_TTL_BALANCE, CACHE_TTL_CAMPAIGNS

logger = logging.getLogger(__name__)


class DjoyaltyCache:
    """
    Loyalty system cache helper।
    Django cache backend wrapper -- graceful fallback if cache unavailable।
    """

    @staticmethod
    def _get_cache():
        try:
            from django.core.cache import cache
            return cache
        except Exception:
            return None

    @staticmethod
    def get_tier(customer_id, tenant_id=None) -> str | None:
        """
        Customer এর cached tier name।
        Returns: tier name string or None
        """
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return None
        key = f'djoyalty:tier:{tenant_id}:{customer_id}'
        try:
            return cache.get(key)
        except Exception as e:
            logger.debug('DjoyaltyCache.get_tier error: %s', e)
            return None

    @staticmethod
    def set_tier(customer_id, tier_name: str, tenant_id=None):
        """Customer এর tier cache করো।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return
        key = f'djoyalty:tier:{tenant_id}:{customer_id}'
        try:
            cache.set(key, tier_name, timeout=CACHE_TTL_TIER)
        except Exception as e:
            logger.debug('DjoyaltyCache.set_tier error: %s', e)

    @staticmethod
    def invalidate_balance(customer_id, tenant_id=None):
        """Customer এর balance cache invalidate করো।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return
        keys = [
            f'djoyalty:balance:{tenant_id}:{customer_id}',
            f'djoyalty:tier:{tenant_id}:{customer_id}',
        ]
        try:
            cache.delete_many(keys)
        except Exception as e:
            logger.debug('DjoyaltyCache.invalidate_balance error: %s', e)

    @staticmethod
    def flush_customer_cache(customer_id, tenant_id=None):
        """Customer এর সব cache flush করো।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return
        keys = [
            f'djoyalty:tier:{tenant_id}:{customer_id}',
            f'djoyalty:balance:{tenant_id}:{customer_id}',
            f'djoyalty:stats:{tenant_id}:{customer_id}',
        ]
        try:
            cache.delete_many(keys)
        except Exception as e:
            logger.debug('DjoyaltyCache.flush_customer_cache error: %s', e)

    @staticmethod
    def invalidate_campaigns(tenant_id=None):
        """Campaign cache invalidate করো।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return
        key = f'djoyalty:campaigns:{tenant_id}'
        try:
            cache.delete(key)
        except Exception as e:
            logger.debug('DjoyaltyCache.invalidate_campaigns error: %s', e)

    @staticmethod
    def get_leaderboard(tenant_id=None, period='all'):
        """Cached leaderboard।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return None
        key = f'djoyalty:leaderboard:{tenant_id}:{period}'
        try:
            return cache.get(key)
        except Exception:
            return None

    @staticmethod
    def set_leaderboard(data, tenant_id=None, period='all'):
        """Leaderboard cache করো।"""
        cache = DjoyaltyCache._get_cache()
        if not cache:
            return
        key = f'djoyalty:leaderboard:{tenant_id}:{period}'
        try:
            from .constants import CACHE_TTL_LEADERBOARD
            cache.set(key, data, timeout=CACHE_TTL_LEADERBOARD)
        except Exception:
            pass

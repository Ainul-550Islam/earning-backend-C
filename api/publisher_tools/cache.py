# api/publisher_tools/cache.py
"""Publisher Tools — Cache management & invalidation."""
from django.core.cache import cache
from .constants import (
    CACHE_TTL_SHORT, CACHE_TTL_MEDIUM, CACHE_TTL_LONG, CACHE_TTL_DAY,
    CACHE_KEY_PREFIX
)
from .utils import build_cache_key


class PublisherCache:
    """Publisher-related cache operations."""

    @staticmethod
    def get_publisher_stats(publisher_id: str, period: str):
        return cache.get(build_cache_key('publisher_stats', publisher_id, period))

    @staticmethod
    def set_publisher_stats(publisher_id: str, period: str, data: dict):
        cache.set(build_cache_key('publisher_stats', publisher_id, period), data, CACHE_TTL_MEDIUM)

    @staticmethod
    def invalidate_publisher(publisher_id: str):
        keys = [
            build_cache_key('publisher_stats', publisher_id, 'today'),
            build_cache_key('publisher_stats', publisher_id, 'last_7_days'),
            build_cache_key('publisher_stats', publisher_id, 'last_30_days'),
            build_cache_key('publisher_dashboard', publisher_id),
            build_cache_key('pub_by_api_key', publisher_id),
        ]
        cache.delete_many(keys)

    @staticmethod
    def get_publisher_dashboard(publisher_id: str):
        return cache.get(build_cache_key('publisher_dashboard', publisher_id))

    @staticmethod
    def set_publisher_dashboard(publisher_id: str, data: dict):
        cache.set(build_cache_key('publisher_dashboard', publisher_id), data, CACHE_TTL_SHORT)


class SiteCache:
    """Site-related cache operations."""

    @staticmethod
    def get_site_analytics(site_id: str, period: str):
        return cache.get(build_cache_key('site_analytics', site_id, period))

    @staticmethod
    def set_site_analytics(site_id: str, period: str, data: dict):
        cache.set(build_cache_key('site_analytics', site_id, period), data, CACHE_TTL_MEDIUM)

    @staticmethod
    def get_site_quality(site_id: str):
        return cache.get(build_cache_key('site_quality', site_id))

    @staticmethod
    def set_site_quality(site_id: str, data: dict):
        cache.set(build_cache_key('site_quality', site_id), data, CACHE_TTL_LONG)

    @staticmethod
    def invalidate_site(site_id: str):
        keys = [
            build_cache_key('site_analytics', site_id, 'today'),
            build_cache_key('site_analytics', site_id, 'last_30_days'),
            build_cache_key('site_quality', site_id),
        ]
        cache.delete_many(keys)


class AdUnitCache:
    """Ad Unit cache operations."""

    @staticmethod
    def get_unit(unit_id: str):
        return cache.get(build_cache_key('ad_unit', unit_id))

    @staticmethod
    def set_unit(unit_id: str, unit):
        cache.set(build_cache_key('ad_unit', unit_id), unit, CACHE_TTL_LONG)

    @staticmethod
    def get_waterfall(group_id: str):
        return cache.get(build_cache_key('waterfall', group_id))

    @staticmethod
    def set_waterfall(group_id: str, items: list):
        cache.set(build_cache_key('waterfall', group_id), items, CACHE_TTL_MEDIUM)

    @staticmethod
    def invalidate_unit(unit_id: str):
        cache.delete(build_cache_key('ad_unit', unit_id))
        cache.delete(build_cache_key('ad_unit', unit_id, 'tag'))
        cache.delete(build_cache_key('ad_unit', unit_id, 'performance'))

    @staticmethod
    def invalidate_waterfall(group_id: str):
        cache.delete(build_cache_key('waterfall', group_id))


class EarningCache:
    """Earning cache operations."""

    @staticmethod
    def get_daily_summary(publisher_id: str, date_str: str):
        return cache.get(build_cache_key('earning_daily', publisher_id, date_str))

    @staticmethod
    def set_daily_summary(publisher_id: str, date_str: str, data: dict):
        cache.set(build_cache_key('earning_daily', publisher_id, date_str), data, CACHE_TTL_LONG)

    @staticmethod
    def invalidate_publisher_earnings(publisher_id: str):
        pattern_keys = [
            build_cache_key('earning_daily', publisher_id),
            build_cache_key('earning_summary', publisher_id),
        ]
        cache.delete_many(pattern_keys)


class FraudCache:
    """Fraud detection cache operations."""

    @staticmethod
    def is_ip_blocked(ip_address: str) -> bool:
        return bool(cache.get(f'blocked_ip:{ip_address}'))

    @staticmethod
    def block_ip(ip_address: str, duration_hours: int = 24):
        cache.set(f'blocked_ip:{ip_address}', True, duration_hours * 3600)

    @staticmethod
    def unblock_ip(ip_address: str):
        cache.delete(f'blocked_ip:{ip_address}')

    @staticmethod
    def get_click_velocity(key: str) -> int:
        return cache.get(f'click_velocity:{key}', 0)

    @staticmethod
    def increment_click_velocity(key: str, window_seconds: int = 60) -> int:
        count = cache.get(f'click_velocity:{key}', 0) + 1
        cache.set(f'click_velocity:{key}', count, window_seconds)
        return count


def clear_all_publisher_caches(publisher_id: str):
    """Publisher-এর সব cache একসাথে clear করে।"""
    PublisherCache.invalidate_publisher(publisher_id)
    EarningCache.invalidate_publisher_earnings(publisher_id)


def warm_publisher_cache(publisher):
    """Publisher cache pre-warm করে।"""
    from .services import PublisherService
    from .utils import get_date_range
    for period in ['today', 'last_7_days', 'last_30_days']:
        stats = PublisherService.get_publisher_dashboard_stats(publisher, period)
        PublisherCache.set_publisher_stats(publisher.publisher_id, period, stats)

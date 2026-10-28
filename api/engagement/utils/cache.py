# engagement/utils/cache.py
from django.core.cache import cache
from ..constants import (
    CACHE_LEADERBOARD, CACHE_USER_STATS, CACHE_STREAK,
    CACHE_SHOP_ITEMS, CACHE_ACHIEVEMENTS,
    CACHE_TTL_SHORT, CACHE_TTL_MEDIUM, CACHE_TTL_LONG,
)


def get_leaderboard_cache(date_str: str, tenant_id=None):
    key = CACHE_LEADERBOARD.format(date=date_str, tenant=tenant_id or "global")
    return cache.get(key)


def set_leaderboard_cache(data, date_str: str, tenant_id=None):
    key = CACHE_LEADERBOARD.format(date=date_str, tenant=tenant_id or "global")
    cache.set(key, data, CACHE_TTL_MEDIUM)


def invalidate_leaderboard_cache(date_str: str, tenant_id=None):
    key = CACHE_LEADERBOARD.format(date=date_str, tenant=tenant_id or "global")
    cache.delete(key)


def get_user_stats_cache(user_id: int):
    return cache.get(CACHE_USER_STATS.format(user_id=user_id))


def set_user_stats_cache(user_id: int, data: dict):
    cache.set(CACHE_USER_STATS.format(user_id=user_id), data, CACHE_TTL_SHORT)


def invalidate_user_stats_cache(user_id: int):
    cache.delete(CACHE_USER_STATS.format(user_id=user_id))


def get_shop_cache(tenant_id=None):
    return cache.get(CACHE_SHOP_ITEMS.format(tenant=tenant_id or "global"))


def set_shop_cache(data, tenant_id=None):
    cache.set(CACHE_SHOP_ITEMS.format(tenant=tenant_id or "global"), data, CACHE_TTL_LONG)


def invalidate_shop_cache(tenant_id=None):
    cache.delete(CACHE_SHOP_ITEMS.format(tenant=tenant_id or "global"))

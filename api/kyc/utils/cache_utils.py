# kyc/utils/cache_utils.py  ── WORLD #1
"""Redis cache helper utilities"""
import logging

logger = logging.getLogger(__name__)


def cache_get(key: str, default=None):
    try:
        from django.core.cache import cache
        return cache.get(key, default)
    except Exception as e:
        logger.warning(f"cache_get failed [{key}]: {e}")
        return default


def cache_set(key: str, value, ttl: int = 300):
    try:
        from django.core.cache import cache
        cache.set(key, value, ttl)
        return True
    except Exception as e:
        logger.warning(f"cache_set failed [{key}]: {e}")
        return False


def cache_delete(key: str):
    try:
        from django.core.cache import cache
        cache.delete(key)
        return True
    except Exception as e:
        logger.warning(f"cache_delete failed [{key}]: {e}")
        return False


def cache_delete_pattern(pattern: str):
    """Delete all keys matching pattern (requires Redis)."""
    try:
        from django.core.cache import cache
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
        return True
    except Exception as e:
        logger.warning(f"cache_delete_pattern failed [{pattern}]: {e}")
        return False


def invalidate_kyc_cache(user_id: int):
    """Invalidate all KYC-related cache for a user."""
    from ..constants import CacheKeys
    keys = [
        CacheKeys.KYC_STATUS.format(user_id=user_id),
        CacheKeys.KYC_SUBMISSION.format(user_id=user_id) if hasattr(CacheKeys, 'KYC_SUBMISSION') else None,
        CacheKeys.KYC_USER_VERIFIED.format(user_id=user_id),
    ]
    for key in keys:
        if key:
            cache_delete(key)


def get_or_set(key: str, callable_fn, ttl: int = 300):
    """Get from cache or compute and store."""
    val = cache_get(key)
    if val is None:
        val = callable_fn()
        cache_set(key, val, ttl)
    return val

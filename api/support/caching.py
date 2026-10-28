# api/support/caching.py
"""
Caching strategies for support system.
Django cache backend wrappers with support-specific patterns.
"""
import logging
import functools
from typing import Any, Callable, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default TTLs
TTL_SHORT  = 30    # Agent status, live counters
TTL_MEDIUM = 300   # Settings, stats
TTL_LONG   = 3600  # KB articles, FAQ lists


def support_cache(key: str, ttl: int = TTL_MEDIUM):
    """
    Decorator: cache function result by key.
    Usage:
        @support_cache('support:faq:list', ttl=600)
        def get_faqs():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, timeout=ttl)
            return result
        return wrapper
    return decorator


def invalidate_support_cache(*keys: str) -> None:
    """Delete multiple cache keys."""
    for key in keys:
        cache.delete(key)
        logger.debug(f'Cache invalidated: {key}')


def get_or_set(key: str, func: Callable, ttl: int = TTL_MEDIUM) -> Any:
    """Get from cache or call func and store result."""
    result = cache.get(key)
    if result is not None:
        return result
    result = func()
    if result is not None:
        cache.set(key, result, timeout=ttl)
    return result


class SupportCacheManager:
    """Manages all support-related cache operations."""

    def warm_up(self) -> dict:
        """Pre-warm critical caches on startup."""
        results = {}

        try:
            from api.support.cache import get_settings
            settings = get_settings()
            results['settings'] = bool(settings)
        except Exception as e:
            results['settings'] = False
            logger.warning(f'Cache warm-up settings: {e}')

        try:
            from api.support.cache import get_ticket_stats
            stats = get_ticket_stats()
            results['stats'] = bool(stats)
        except Exception as e:
            results['stats'] = False

        try:
            from api.support.models import FAQ
            faqs = list(FAQ.objects.filter(is_active=True).order_by('order')[:50])
            cache.set('support:faq:list:all', faqs, timeout=TTL_LONG)
            results['faqs'] = len(faqs)
        except Exception as e:
            results['faqs'] = 0

        logger.info(f'Cache warm-up: {results}')
        return results

    def flush_all(self) -> None:
        """Flush all support caches. Use with caution."""
        keys_to_clear = [
            'support:settings:singleton',
            'support:maintenance_mode',
            'support:faq:list:all',
            'support:stats:tickets:global',
            'support:announcements:global',
            'support:kb:categories:global',
        ]
        for key in keys_to_clear:
            cache.delete(key)
        logger.info('Support cache flushed')

    def flush_user(self, user_id: int) -> None:
        """Flush all caches for a specific user."""
        user_keys = [
            f'support:user:tickets:{user_id}',
            f'support:integ:wallet:balance:{user_id}',
            f'support:integ:fraud:risk:{user_id}',
            f'support:integ:kyc:status:{user_id}',
        ]
        for key in user_keys:
            cache.delete(key)

    def flush_ticket(self, ticket_id: str) -> None:
        """Flush ticket-specific caches."""
        cache.delete(f'support:ticket:{ticket_id}')

    def get_cache_stats(self) -> dict:
        """Try to get cache memory stats (Redis only)."""
        try:
            from django_redis import get_redis_connection
            r     = get_redis_connection('default')
            info  = r.info('memory')
            return {
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': r.info('clients').get('connected_clients', 0),
            }
        except Exception:
            return {'status': 'Cache stats unavailable (non-Redis backend)'}


cache_manager = SupportCacheManager()
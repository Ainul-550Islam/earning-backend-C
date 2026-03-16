# api/cache/integration.py
"""
Cache integration for services. Use this in wallet, tasks, etc. for performance.
Production-ready with error handling and logging.
"""
import logging
from typing import Any, Optional, Callable
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes
WALLET_BALANCE_TTL = 60
TASK_LIST_TTL = 30


def get_cached(key: str, builder: Optional[Callable[[], Any]] = None, ttl: int = DEFAULT_TTL) -> Any:
    """
    Get value from cache, or compute via builder and store.
    Returns None on cache/ builder error.
    """
    try:
        value = cache.get(key)
        if value is not None:
            return value
        if builder is not None:
            value = builder()
            cache.set(key, value, timeout=ttl)
            return value
    except Exception as e:
        logger.warning("Cache get_cached error for key %s: %s", key, e)
    return None


def invalidate_pattern(prefix: str) -> None:
    """Invalidate keys by prefix. No-op if backend doesn't support delete_pattern."""
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(prefix)
        else:
            cache.delete(prefix)
    except Exception as e:
        logger.debug("Cache invalidate_pattern %s: %s", prefix, e)


def wallet_balance_key(user_id: int) -> str:
    return f"wallet_balance:{user_id}"


def task_list_key(user_id: Optional[int], system_type: Optional[str] = None) -> str:
    parts = ["task_list", f"u{user_id or 0}"]
    if system_type:
        parts.append(system_type)
    return ":".join(parts)


def get_wallet_balance_cached(user_id: int, builder: Callable[[], Any]) -> Any:
    """Cached wallet balance for user. Invalidate on transaction."""
    return get_cached(wallet_balance_key(user_id), builder, ttl=WALLET_BALANCE_TTL)


def invalidate_wallet_cache(user_id: int) -> None:
    """Call after wallet/transaction changes."""
    try:
        cache.delete(wallet_balance_key(user_id))
    except Exception as e:
        logger.debug("invalidate_wallet_cache: %s", e)


def invalidate_task_list_cache(user_id: Optional[int] = None) -> None:
    """Call after task/completion changes."""
    try:
        if user_id is not None:
            cache.delete(task_list_key(user_id, None))
        invalidate_pattern("task_list:*")
    except Exception as e:
        logger.debug("invalidate_task_list_cache: %s", e)

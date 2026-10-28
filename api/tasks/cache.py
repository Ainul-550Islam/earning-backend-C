"""
tasks/cache.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cache helper classes used across task modules.
Wraps Django's cache backend with domain-specific key namespacing.
"""

import logging
from typing import Any, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default TTLs (seconds)
_TTL_SHORT  = 60
_TTL_MEDIUM = 300
_TTL_LONG   = 3600


class PICache:
    """
    Publisher/IP Cache — fast key-value store for IP management tasks.
    Namespaces all keys under 'pi:' to avoid collisions.
    """

    PREFIX = 'pi'

    @classmethod
    def _key(cls, *parts: str) -> str:
        return f"{cls.PREFIX}:" + ":".join(str(p) for p in parts)

    # ── IP blacklist / whitelist ──────────────────────────────────────────────

    @classmethod
    def get_ip_status(cls, ip: str) -> Optional[str]:
        return cache.get(cls._key('ip', ip))

    @classmethod
    def set_ip_status(cls, ip: str, status: str, ttl: int = _TTL_LONG) -> None:
        cache.set(cls._key('ip', ip), status, ttl)

    @classmethod
    def delete_ip_status(cls, ip: str) -> None:
        cache.delete(cls._key('ip', ip))

    # ── Rate limiting counters ────────────────────────────────────────────────

    @classmethod
    def increment_ip_counter(cls, ip: str, window: str = '1h') -> int:
        key = cls._key('rate', ip, window)
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, _TTL_LONG)
            return 1

    @classmethod
    def get_ip_counter(cls, ip: str, window: str = '1h') -> int:
        return cache.get(cls._key('rate', ip, window), 0)

    # ── Publisher reputation cache ────────────────────────────────────────────

    @classmethod
    def get_publisher_score(cls, publisher_id: Any) -> Optional[float]:
        return cache.get(cls._key('pub_score', publisher_id))

    @classmethod
    def set_publisher_score(cls, publisher_id: Any, score: float, ttl: int = _TTL_MEDIUM) -> None:
        cache.set(cls._key('pub_score', publisher_id), score, ttl)

    # ── Generic helpers ───────────────────────────────────────────────────────

    @classmethod
    def get(cls, *key_parts: str) -> Optional[Any]:
        return cache.get(cls._key(*key_parts))

    @classmethod
    def set(cls, *key_parts_and_value, ttl: int = _TTL_MEDIUM) -> None:
        """set('a', 'b', value, ttl=300) — last positional arg is the value."""
        *parts, value = key_parts_and_value
        cache.set(cls._key(*parts), value, ttl)

    @classmethod
    def delete(cls, *key_parts: str) -> None:
        cache.delete(cls._key(*key_parts))

    @classmethod
    def flush_prefix(cls, sub_prefix: str) -> None:
        """Best-effort prefix flush (works with LocMemCache; Redis needs scan)."""
        try:
            cache.delete_pattern(f"{cls.PREFIX}:{sub_prefix}:*")
        except AttributeError:
            logger.debug("Cache backend does not support delete_pattern; skipping flush.")


__all__ = ['PICache']

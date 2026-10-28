"""
NEW FILE — Centralized cache key management for flag evaluation.

DRY FIX: the string `f"flag_enabled:{flag_name}"` was hand-built in at
least 5 different files (flag_engine.py, signals.py,
services/feature_flag_service.py, services/rollout_service.py,
viewsets/feature_flag_viewset.py). A typo or naming change in one place
would silently desync caches. Centralized here.

BUG FIX: the original `FlagEngine.clear_all_cache()` called
`cache.delete_many(cache.keys("flag_enabled:*"))`. `cache.keys(pattern)` is
a django-redis-only extension method — it does not exist on Django's
built-in LocMemCache/FileBasedCache/DatabaseCache backends, so this raised
`AttributeError` in any project not specifically configured with
django-redis. `clear_all_cache()` below uses a versioned-key strategy
instead, which works on every Django cache backend.
"""
from django.core.cache import cache

FLAG_CACHE_PREFIX = 'flag_enabled'
FLAG_VALUE_CACHE_PREFIX = 'flag_value'
CACHE_VERSION_KEY = 'flag_cache_version'
DEFAULT_TIMEOUT = 300  # 5 minutes


class FlagCacheManager:
    """Single source of truth for feature-flag cache key naming & invalidation."""

    @staticmethod
    def _version() -> int:
        version = cache.get(CACHE_VERSION_KEY)
        if version is None:
            version = 1
            cache.set(CACHE_VERSION_KEY, version, None)  # never expires on its own
        return version

    @classmethod
    def enabled_key(cls, flag_name: str, environment: str = 'production') -> str:
        return f"{FLAG_CACHE_PREFIX}:v{cls._version()}:{environment}:{flag_name}"

    @classmethod
    def value_key(cls, flag_name: str, environment: str = 'production') -> str:
        return f"{FLAG_VALUE_CACHE_PREFIX}:v{cls._version()}:{environment}:{flag_name}"

    @classmethod
    def get_enabled(cls, flag_name: str, environment: str = 'production'):
        return cache.get(cls.enabled_key(flag_name, environment))

    @classmethod
    def set_enabled(cls, flag_name: str, value: bool, environment: str = 'production', timeout: int = DEFAULT_TIMEOUT):
        cache.set(cls.enabled_key(flag_name, environment), value, timeout)

    @classmethod
    def clear_flag_cache(cls, flag_name: str, environment: str = 'production') -> None:
        """Clear cache for one specific flag (called from signals on save/delete)."""
        cache.delete(cls.enabled_key(flag_name, environment))
        cache.delete(cls.value_key(flag_name, environment))

    @classmethod
    def clear_all_cache(cls) -> None:
        """
        Invalidate ALL flag caches across every backend, including ones that
        don't support key pattern scanning (LocMemCache, FileBasedCache,
        DatabaseCache). Works by bumping a version number that's baked into
        every cache key, making old entries unreachable (they'll simply
        expire naturally via their TTL).
        """
        try:
            cache.incr(CACHE_VERSION_KEY)
        except ValueError:
            # Key didn't exist yet
            cache.set(CACHE_VERSION_KEY, 2, None)

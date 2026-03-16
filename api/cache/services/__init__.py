# api/cache/services/__init__.py
"""Cache services - Redis, Memcached, CacheInvalidator."""

try:
    from api.cache.services.CacheService import CacheService
except ImportError:
    CacheService = None

try:
    from api.cache.services.RedisService import RedisService
except ImportError:
    RedisService = None

try:
    from api.cache.services.MemcachedService import MemcachedService
except ImportError:
    MemcachedService = None

try:
    from api.cache.services.CacheInvalidator import CacheInvalidator, create_cache_invalidator
except ImportError:
    CacheInvalidator = None
    create_cache_invalidator = None

__all__ = [
    'CacheService',
    'RedisService',
    'MemcachedService',
    'CacheInvalidator',
    'create_cache_invalidator',
]
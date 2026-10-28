"""
Cache Manager for alerts app - Advanced caching system
"""
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import logging
import json
import time
import hashlib
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """Cache backend enumeration"""
    DJANGO = "django"
    REDIS = "redis"
    MEMCACHED = "memcached"
    MEMORY = "memory"


class CacheStrategy(Enum):
    """Cache strategy enumeration"""
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"
    REFRESH_AHEAD = "refresh_ahead"


class CacheEntry:
    """Represents a cache entry"""
    
    def __init__(self, key: str, value: Any, ttl: int = None):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.created_at = timezone.now()
        self.access_count = 0
        self.last_accessed = None
        self.size = len(json.dumps(value, default=str)) if not isinstance(value, str) else len(value)
        
    def access(self) -> Any:
        """Access the cache entry"""
        self.access_count += 1
        self.last_accessed = timezone.now()
        return self.value
    
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl is None:
            return False
        
        return timezone.now() > self.created_at + timedelta(seconds=self.ttl)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'key': self.key,
            'value': self.value,
            'ttl': self.ttl,
            'created_at': self.created_at.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'size': self.size,
            'is_expired': self.is_expired()
        }


class MemoryCache:
    """In-memory cache implementation"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache = {}
        self._access_order = []
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats['misses'] += 1
            return None
        
        if entry.is_expired():
            self.delete(key)
            self._stats['misses'] += 1
            return None
        
        self._stats['hits'] += 1
        self._update_access_order(key)
        return entry.access()
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        if ttl is None:
            ttl = self.default_ttl
        
        entry = CacheEntry(key, value, ttl)
        
        # Check if we need to evict
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()
        
        self._cache[key] = entry
        self._update_access_order(key)
        self._stats['sets'] += 1
        
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]
            self._remove_from_access_order(key)
            self._stats['deletes'] += 1
            return True
        
        return False
    
    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        self._access_order.clear()
        
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._access_order:
            return
        
        lru_key = self._access_order.pop(0)
        if lru_key in self._cache:
            del self._cache[lru_key]
            self._stats['evictions'] += 1
    
    def _update_access_order(self, key: str):
        """Update access order for LRU"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def _remove_from_access_order(self, key: str):
        """Remove key from access order"""
        if key in self._access_order:
            self._access_order.remove(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests) if total_requests > 0 else 0
        
        return {
            'backend': 'memory',
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'evictions': self._stats['evictions']
        }


class CacheManager:
    """Advanced cache management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backend_type = CacheBackend(config.get('backend', 'django'))
        self.default_ttl = config.get('default_ttl', 3600)
        self.key_prefix = config.get('key_prefix', 'alerts')
        self.compression_enabled = config.get('compression_enabled', False)
        self.serialization_enabled = config.get('serialization_enabled', True)
        
        # Initialize backend
        self.backend = self._initialize_backend()
        
        # Cache statistics
        self.stats = {
            'gets': 0,
            'sets': 0,
            'deletes': 0,
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
        
    def _initialize_backend(self):
        """Initialize cache backend"""
        if self.backend_type == CacheBackend.MEMORY:
            return MemoryCache(
                max_size=self.config.get('memory_max_size', 1000),
                default_ttl=self.default_ttl
            )
        elif self.backend_type == CacheBackend.REDIS:
            return self._initialize_redis_backend()
        elif self.backend_type == CacheBackend.MEMCACHED:
            return self._initialize_memcached_backend()
        else:
            # Use Django cache as default
            return cache
    
    def _initialize_redis_backend(self):
        """Initialize Redis backend"""
        try:
            import redis
            
            redis_config = self.config.get('redis', {})
            redis_client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True
            )
            
            class RedisBackend:
                def __init__(self, client):
                    self.client = client
                
                def get(self, key):
                    try:
                        value = self.client.get(key)
                        if value is not None:
                            return json.loads(value) if self.serialization_enabled else value
                        return None
                    except Exception as e:
                        logger.error(f"Redis get error: {e}")
                        return None
                
                def set(self, key, value, ttl=None):
                    try:
                        if self.serialization_enabled and not isinstance(value, str):
                            value = json.dumps(value, default=str)
                        
                        return self.client.setex(key, ttl or self.default_ttl, value)
                    except Exception as e:
                        logger.error(f"Redis set error: {e}")
                        return False
                
                def delete(self, key):
                    try:
                        return bool(self.client.delete(key))
                    except Exception as e:
                        logger.error(f"Redis delete error: {e}")
                        return False
                
                def clear(self):
                    try:
                        return self.client.flushdb()
                    except Exception as e:
                        logger.error(f"Redis clear error: {e}")
                        return False
            
            return RedisBackend(redis_client)
            
        except ImportError:
            logger.error("Redis not available, falling back to Django cache")
            return cache
    
    def _initialize_memcached_backend(self):
        """Initialize Memcached backend"""
        try:
            import pylibmc
            
            memcached_config = self.config.get('memcached', {})
            servers = memcached_config.get('servers', ['localhost:11211'])
            
            class MemcachedBackend:
                def __init__(self, servers):
                    self.client = pylibmc.Client(servers, binary=True)
                
                def get(self, key):
                    try:
                        value = self.client.get(key)
                        if value is not None:
                            return json.loads(value) if self.serialization_enabled else value
                        return None
                    except Exception as e:
                        logger.error(f"Memcached get error: {e}")
                        return None
                
                def set(self, key, value, ttl=None):
                    try:
                        if self.serialization_enabled and not isinstance(value, str):
                            value = json.dumps(value, default=str)
                        
                        return self.client.set(key, value, time=ttl or self.default_ttl)
                    except Exception as e:
                        logger.error(f"Memcached set error: {e}")
                        return False
                
                def delete(self, key):
                    try:
                        return bool(self.client.delete(key))
                    except Exception as e:
                        logger.error(f"Memcached delete error: {e}")
                        return False
                
                def clear(self):
                    try:
                        return self.client.flush_all()
                    except Exception as e:
                        logger.error(f"Memcached clear error: {e}")
                        return False
            
            return MemcachedBackend(servers)
            
        except ImportError:
            logger.error("Memcached not available, falling back to Django cache")
            return cache
    
    def _make_key(self, key: str) -> str:
        """Create full cache key with prefix"""
        return f"{self.key_prefix}:{key}"
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for caching"""
        if not self.serialization_enabled:
            return value
        
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        
        return value
    
    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize value from cache"""
        if not self.serialization_enabled:
            return value
        
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            full_key = self._make_key(key)
            self.stats['gets'] += 1
            
            if hasattr(self.backend, 'get'):
                value = self.backend.get(full_key)
            else:
                value = cache.get(full_key)
            
            if value is not None:
                self.stats['hits'] += 1
                return self._deserialize_value(value)
            else:
                self.stats['misses'] += 1
                return default
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache get error: {e}")
            return default
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        try:
            full_key = self._make_key(key)
            serialized_value = self._serialize_value(value)
            cache_ttl = ttl or self.default_ttl
            
            self.stats['sets'] += 1
            
            if hasattr(self.backend, 'set'):
                return self.backend.set(full_key, serialized_value, cache_ttl)
            else:
                return cache.set(full_key, serialized_value, cache_ttl)
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            full_key = self._make_key(key)
            self.stats['deletes'] += 1
            
            if hasattr(self.backend, 'delete'):
                return self.backend.delete(full_key)
            else:
                return cache.delete(full_key)
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache entries"""
        try:
            if hasattr(self.backend, 'clear'):
                return self.backend.clear()
            else:
                return cache.clear()
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        result = {}
        
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        
        return result
    
    def set_many(self, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple values in cache"""
        success = True
        
        for key, value in data.items():
            if not self.set(key, value, ttl):
                success = False
        
        return success
    
    def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys from cache"""
        deleted_count = 0
        
        for key in keys:
            if self.delete(key):
                deleted_count += 1
        
        return deleted_count
    
    def increment(self, key: str, delta: int = 1, ttl: int = None) -> int:
        """Increment numeric value in cache"""
        try:
            full_key = self._make_key(key)
            self.stats['sets'] += 1
            
            if hasattr(self.backend, 'get') and hasattr(self.backend, 'set'):
                # Custom implementation for backends that don't support increment
                current_value = self.get(key, 0)
                new_value = current_value + delta
                self.set(key, new_value, ttl)
                return new_value
            else:
                # Use Django cache increment if available
                if hasattr(cache, 'incr'):
                    return cache.incr(full_key, delta)
                else:
                    # Fallback to get-set pattern
                    current_value = self.get(key, 0)
                    new_value = current_value + delta
                    self.set(key, new_value, ttl)
                    return new_value
                    
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Cache increment error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['gets']
        hit_rate = (self.stats['hits'] / total_requests) if total_requests > 0 else 0
        
        stats = {
            'backend_type': self.backend_type.value,
            'key_prefix': self.key_prefix,
            'default_ttl': self.default_ttl,
            'compression_enabled': self.compression_enabled,
            'serialization_enabled': self.serialization_enabled,
            'stats': self.stats.copy(),
            'hit_rate': hit_rate
        }
        
        # Add backend-specific stats
        if hasattr(self.backend, 'get_stats'):
            backend_stats = self.backend.get_stats()
            stats['backend_stats'] = backend_stats
        
        return stats
    
    def warm_cache(self, data: Dict[str, Any], ttl: int = None):
        """Warm cache with initial data"""
        logger.info(f"Warming cache with {len(data)} entries")
        
        success = self.set_many(data, ttl)
        
        if success:
            logger.info("Cache warmed successfully")
        else:
            logger.warning("Some cache entries failed to warm")
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        try:
            if self.backend_type == CacheBackend.REDIS:
                # Redis pattern matching
                import redis
                if hasattr(self.backend, 'client'):
                    keys = self.backend.client.keys(f"{self.key_prefix}:{pattern}")
                    if keys:
                        return self.backend.client.delete(*keys)
            
            elif self.backend_type == CacheBackend.MEMORY:
                # Memory cache pattern matching
                import re
                regex_pattern = re.compile(pattern.replace('*', '.*'))
                keys_to_delete = [
                    key for key in self.backend._cache.keys()
                    if regex_pattern.match(key)
                ]
                
                for key in keys_to_delete:
                    self.backend.delete(key)
                
                return len(keys_to_delete)
            
            else:
                # For other backends, try to get all keys and filter
                # This is backend-dependent and may not be efficient
                logger.warning("Pattern invalidation not supported for this backend")
                return 0
                
        except Exception as e:
            logger.error(f"Cache pattern invalidation error: {e}")
            return 0


# Global cache manager
cache_manager = None


def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager"""
    return cache_manager


def initialize_cache_manager():
    """Initialize cache manager from settings"""
    from django.conf import settings
    
    global cache_manager
    
    config = getattr(settings, 'CACHE_MANAGER_CONFIG', {
        'backend': 'django',
        'default_ttl': 3600,
        'key_prefix': 'alerts',
        'compression_enabled': False,
        'serialization_enabled': True,
        'memory_max_size': 1000,
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        'memcached': {
            'servers': ['localhost:11211']
        }
    })
    
    try:
        cache_manager = CacheManager(config)
        logger.info("Cache manager initialized")
    except Exception as e:
        logger.error(f"Error initializing cache manager: {e}")


# Decorator for caching function results
def cached(key_template: str, ttl: int = None, cache_manager_instance: CacheManager = None):
    """Decorator to cache function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_template.format(*args, **kwargs)
            
            # Try to get from cache
            cm = cache_manager_instance or get_cache_manager()
            if cm:
                cached_result = cm.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            if cm:
                cm.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Initialize on module import
try:
    initialize_cache_manager()
except Exception as e:
    logger.error(f"Error initializing cache manager: {e}")

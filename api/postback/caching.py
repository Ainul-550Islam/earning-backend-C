"""
caching.py – Caching system for postback module.

Provides comprehensive caching functionality including:
- Multi-level caching strategies
- Cache invalidation and expiration
- Cache warming and preloading
- Performance monitoring
"""
from typing import Set
import logging
from typing import Dict, List, Optional, Any, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import time
import hashlib
import pickle
import json

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache level enumeration."""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DATABASE = "l3_database"


class CacheStrategy(Enum):
    """Cache strategy enumeration."""
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    WRITE_AROUND = "write_around"


class CacheStatus(Enum):
    """Cache status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    WARMING = "warming"
    EVICTING = "evicting"


@dataclass
class CacheEntry:
    """Cache entry data structure."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=timezone.now)
    last_accessed: datetime = field(default_factory=timezone.now)
    access_count: int = 0
    ttl: Optional[int] = None
    expires_at: Optional[datetime] = None
    size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def update_access(self):
        """Update access information."""
        self.last_accessed = timezone.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'key': self.key,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'ttl': self.ttl,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'size': self.size,
            'metadata': self.metadata,
        }


class MemoryCache:
    """
    In-memory cache implementation.
    
    Provides fast L1 caching with LRU eviction.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0,
            'expirations': 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            entry = self.cache.get(key)
            
            if entry is None:
                self.stats['misses'] += 1
                return None
            
            if entry.is_expired():
                del self.cache[key]
                self.access_order.remove(key)
                self.stats['expirations'] += 1
                self.stats['misses'] += 1
                return None
            
            # Update access order for LRU
            self.access_order.remove(key)
            self.access_order.append(key)
            entry.update_access()
            
            self.stats['hits'] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache."""
        with self.lock:
            # Calculate TTL and expiration
            if ttl is None:
                ttl = self.default_ttl
            
            expires_at = None
            if ttl > 0:
                expires_at = timezone.now() + timedelta(seconds=ttl)
            
            # Calculate size
            size = self._calculate_size(value)
            
            # Check if eviction is needed
            if key not in self.cache and len(self.cache) >= self.max_size:
                self._evict_lru()
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                expires_at=expires_at,
                size=size
            )
            
            # Update cache and access order
            if key in self.cache:
                self.access_order.remove(key)
            
            self.cache[key] = entry
            self.access_order.append(key)
            self.stats['sets'] += 1
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.access_order.remove(key)
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if self.access_order:
            lru_key = self.access_order[0]
            del self.cache[lru_key]
            self.access_order.pop(0)
            self.stats['evictions'] += 1
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate size of cached value."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return len(str(value))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'sets': self.stats['sets'],
            'evictions': self.stats['evictions'],
            'expirations': self.stats['expirations'],
        }
    
    def get_keys(self) -> List[str]:
        """Get all cache keys."""
        with self.lock:
            return list(self.cache.keys())
    
    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry."""
        with self.lock:
            return self.cache.get(key)


class CacheManager:
    """
    Multi-level cache manager.
    
    Manages caching across multiple levels with
    different strategies and policies.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.l1_cache = MemoryCache(
            max_size=getattr(settings, 'CACHE_L1_MAX_SIZE', 1000),
            default_ttl=getattr(settings, 'CACHE_L1_DEFAULT_TTL', 300)
        )
        self.l2_cache = cache  # Django's cache (typically Redis)
        self.cache_levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        self.default_strategy = CacheStrategy.LRU
        self.warming_keys: Set[str] = set()
        self.warming = False
        self.warm_thread = None
        self._setup_default_config()
    
    def _setup_default_config(self):
        """Setup default cache configuration."""
        self.cache_config = {
            'postback_data': {
                'ttl': 3600,  # 1 hour
                'levels': [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
                'strategy': CacheStrategy.TTL,
            },
            'analytics_data': {
                'ttl': 1800,  # 30 minutes
                'levels': [CacheLevel.L1_MEMORY],
                'strategy': CacheStrategy.LRU,
            },
            'user_sessions': {
                'ttl': 7200,  # 2 hours
                'levels': [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
                'strategy': CacheStrategy.LRU,
            },
            'config_data': {
                'ttl': 86400,  # 24 hours
                'levels': [CacheLevel.L2_REDIS],
                'strategy': CacheStrategy.TTL,
            },
        }
    
    def get(self, key: str, level: CacheLevel = None) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            level: Specific cache level to check
            
        Returns:
            Cached value or None
        """
        if level:
            return self._get_from_level(key, level)
        
        # Try each level in order
        for cache_level in self.cache_levels:
            value = self._get_from_level(key, cache_level)
            if value is not None:
                # Promote to higher levels
                self._promote_to_levels(key, value, cache_level)
                return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None, levels: List[CacheLevel] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            levels: Cache levels to use
            
        Returns:
            True if set successfully
        """
        if levels is None:
            levels = self.cache_levels
        
        success = True
        
        for cache_level in levels:
            if not self._set_to_level(key, value, ttl, cache_level):
                success = False
        
        return success
    
    def delete(self, key: str, level: CacheLevel = None) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            level: Specific cache level
            
        Returns:
            True if deleted successfully
        """
        if level:
            return self._delete_from_level(key, level)
        
        success = True
        for cache_level in self.cache_levels:
            if not self._delete_from_level(key, cache_level):
                success = False
        
        return success
    
    def _get_from_level(self, key: str, level: CacheLevel) -> Optional[Any]:
        """Get value from specific cache level."""
        if level == CacheLevel.L1_MEMORY:
            return self.l1_cache.get(key)
        elif level == CacheLevel.L2_REDIS:
            try:
                return cache.get(key)
            except Exception as e:
                self.logger.error(f"L2 cache get error: {str(e)}")
                return None
        
        return None
    
    def _set_to_level(self, key: str, value: Any, ttl: int, level: CacheLevel) -> bool:
        """Set value in specific cache level."""
        try:
            if level == CacheLevel.L1_MEMORY:
                return self.l1_cache.set(key, value, ttl)
            elif level == CacheLevel.L2_REDIS:
                return cache.set(key, value, ttl)
        except Exception as e:
            self.logger.error(f"Cache set error for {level.value}: {str(e)}")
            return False
        
        return True
    
    def _delete_from_level(self, key: str, level: CacheLevel) -> bool:
        """Delete key from specific cache level."""
        try:
            if level == CacheLevel.L1_MEMORY:
                return self.l1_cache.delete(key)
            elif level == CacheLevel.L2_REDIS:
                return cache.delete(key)
        except Exception as e:
            self.logger.error(f"Cache delete error for {level.value}: {str(e)}")
            return False
        
        return True
    
    def _promote_to_levels(self, key: str, value: Any, source_level: CacheLevel):
        """Promote value to higher cache levels."""
        # Find levels higher than source
        higher_levels = []
        for i, level in enumerate(self.cache_levels):
            if level == source_level:
                higher_levels = self.cache_levels[:i]
                break
        
        # Set in higher levels
        for level in higher_levels:
            self._set_to_level(key, value, None, level)
    
    def warm_cache(self, keys: List[str], load_function: Callable[[str], Any]):
        """
        Warm cache with preloaded data.
        
        Args:
            keys: Keys to warm
            load_function: Function to load data for keys
        """
        self.warming_keys.update(keys)
        
        if not self.warming:
            self.warming = True
            self.warm_thread = threading.Thread(
                target=self._warm_cache_worker,
                args=(keys, load_function),
                daemon=True
            )
            self.warm_thread.start()
    
    def _warm_cache_worker(self, keys: List[str], load_function: Callable[[str], Any]):
        """Cache warming worker thread."""
        for key in keys:
            if key not in self.warming_keys:
                continue
            
            try:
                # Check if already cached
                if self.get(key) is not None:
                    continue
                
                # Load and cache data
                value = load_function(key)
                if value is not None:
                    self.set(key, value)
                    self.logger.debug(f"Warmed cache key: {key}")
            
            except Exception as e:
                self.logger.error(f"Error warming cache key {key}: {str(e)}")
            
            finally:
                self.warming_keys.discard(key)
        
        self.warming = False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache keys matching pattern.
        
        Args:
            pattern: Pattern to match (supports wildcards)
            
        Returns:
            Number of keys invalidated
        """
        import fnmatch
        
        invalidated = 0
        
        # Invalidate L1 cache
        l1_keys = self.l1_cache.get_keys()
        for key in l1_keys:
            if fnmatch.fnmatch(key, pattern):
                if self.l1_cache.delete(key):
                    invalidated += 1
        
        # Invalidate L2 cache (if supported)
        try:
            # This would require Redis pattern matching
            # For now, just log
            self.logger.info(f"Would invalidate L2 cache pattern: {pattern}")
        except Exception as e:
            self.logger.error(f"Error invalidating L2 cache pattern: {str(e)}")
        
        self.logger.info(f"Invalidated {invalidated} cache keys matching pattern: {pattern}")
        return invalidated
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'l1_cache': self.l1_cache.get_stats(),
            'warming': self.warming,
            'warming_keys': len(self.warming_keys),
        }
        
        # L2 cache stats (if available)
        try:
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'info'):
                stats['l2_cache'] = cache._cache.info()
        except Exception:
            pass
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform cache health check."""
        health_status = {
            'overall': 'healthy',
            'l1_cache': 'healthy',
            'l2_cache': 'healthy',
            'issues': [],
        }
        
        # Check L1 cache
        l1_stats = self.l1_cache.get_stats()
        if l1_stats['hit_rate'] < 50:
            health_status['l1_cache'] = 'degraded'
            health_status['issues'].append(f"Low L1 cache hit rate: {l1_stats['hit_rate']:.1f}%")
        
        # Check L2 cache
        try:
            # Test L2 cache connectivity
            test_key = f"health_check_{int(time.time())}"
            if cache.set(test_key, "test", timeout=10):
                if cache.get(test_key) == "test":
                    cache.delete(test_key)
                else:
                    health_status['l2_cache'] = 'unhealthy'
                    health_status['issues'].append("L2 cache read/write test failed")
            else:
                health_status['l2_cache'] = 'unhealthy'
                health_status['issues'].append("L2 cache write test failed")
        
        except Exception as e:
            health_status['l2_cache'] = 'unhealthy'
            health_status['issues'].append(f"L2 cache error: {str(e)}")
        
        # Determine overall status
        if 'unhealthy' in [health_status['l1_cache'], health_status['l2_cache']]:
            health_status['overall'] = 'unhealthy'
        elif 'degraded' in [health_status['l1_cache'], health_status['l2_cache']]:
            health_status['overall'] = 'degraded'
        
        return health_status


# Global cache manager instance
cache_manager = CacheManager()


# Decorators for caching
def cache_result(key_func: Callable = None, ttl: int = 300, levels: List[CacheLevel] = None):
    """
    Decorator for caching function results.
    
    Args:
        key_func: Function to generate cache key
        ttl: Time to live in seconds
        levels: Cache levels to use
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{hashlib.md5(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache_manager.set(cache_key, result, ttl, levels)
            
            return result
        return wrapper
    return decorator


def cache_invalidate(key_func: Callable = None):
    """
    Decorator for invalidating cache after function execution.
    
    Args:
        key_func: Function to generate cache key
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Invalidate cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{hashlib.md5(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()}"
            
            cache_manager.delete(cache_key)
            
            return result
        return wrapper
    return decorator


# Convenience functions
def get_cached(key: str, level: CacheLevel = None) -> Optional[Any]:
    """Get value from cache."""
    return cache_manager.get(key, level)


def set_cached(key: str, value: Any, ttl: int = None, levels: List[CacheLevel] = None) -> bool:
    """Set value in cache."""
    return cache_manager.set(key, value, ttl, levels)


def delete_cached(key: str, level: CacheLevel = None) -> bool:
    """Delete key from cache."""
    return cache_manager.delete(key, level)


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate cache keys matching pattern."""
    return cache_manager.invalidate_pattern(pattern)


def warm_cache(keys: List[str], load_function: Callable[[str], Any]):
    """Warm cache with preloaded data."""
    cache_manager.warm_cache(keys, load_function)


def get_cache_statistics() -> Dict[str, Any]:
    """Get cache statistics."""
    return cache_manager.get_statistics()


def perform_cache_health_check() -> Dict[str, Any]:
    """Perform cache health check."""
    return cache_manager.health_check()


# Utility functions for common caching patterns
def cache_postback_data(postback_id: str, data: Dict[str, Any], ttl: int = 3600):
    """Cache postback data."""
    key = f"postback:{postback_id}"
    return set_cached(key, data, ttl)


def get_postback_data(postback_id: str):
    """Get cached postback data."""
    key = f"postback:{postback_id}"
    return get_cached(key)


def cache_user_session(user_id: int, session_data: Dict[str, Any], ttl: int = 7200):
    """Cache user session data."""
    key = f"user_session:{user_id}"
    return set_cached(key, session_data, ttl)


def get_user_session(user_id: int):
    """Get cached user session data."""
    key = f"user_session:{user_id}"
    return get_cached(key)


def cache_analytics_data(data_type: str, key: str, data: Any, ttl: int = 1800):
    """Cache analytics data."""
    cache_key = f"analytics:{data_type}:{key}"
    return set_cached(cache_key, data, ttl)


def get_analytics_data(data_type: str, key: str):
    """Get cached analytics data."""
    cache_key = f"analytics:{data_type}:{key}"
    return get_cached(cache_key)

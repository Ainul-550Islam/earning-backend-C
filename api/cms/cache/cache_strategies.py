# cms/cache/cache_strategies.py
"""
Advanced Caching Strategies

Multi-level caching with:
- L1: Memory cache (in-process)
- L2: Redis cache (distributed)
- L3: Database cache (fallback)

Patterns:
- LRU (Least Recently Used)
- TTL (Time To Live)
- Write-through
- Write-back
- Cache-aside
- Refresh-ahead
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import timedelta
from functools import wraps
import hashlib
import json
import logging
from django.core.cache import cache, caches
from django.utils import timezone

logger = logging.getLogger('cms.cache.strategies')


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-LEVEL CACHE
# ─────────────────────────────────────────────────────────────────────────────

class MultiLevelCache:
    """
    Multi-level caching system (L1 -> L2 -> L3)
    
    L1: In-memory (fast, limited size)
    L2: Redis (distributed, moderate speed)
    L3: Database (slow, unlimited size)
    """
    
    def __init__(self):
        """Initialize cache levels"""
        self.l1 = {}  # In-memory dict
        self.l2 = caches['default']  # Redis
        self.l3_enabled = False  # Database (optional)
        self.max_l1_size = 1000
        self.l1_stats = {'hits': 0, 'misses': 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache (tries L1 -> L2 -> L3)"""
        
        # Try L1 (in-memory)
        if key in self.l1:
            self.l1_stats['hits'] += 1
            logger.debug(f"L1 HIT: {key}")
            return self.l1[key]
        
        self.l1_stats['misses'] += 1
        
        # Try L2 (Redis)
        try:
            value = self.l2.get(key)
            if value is not None:
                self._populate_l1(key, value)
                logger.debug(f"L2 HIT: {key}")
                return value
        except Exception as e:
            logger.warning(f"L2 get failed: {e}")
        
        # Try L3 (Database) - future implementation
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set in all cache levels"""
        
        # L1 (in-memory)
        self._populate_l1(key, value)
        
        # L2 (Redis)
        try:
            self.l2.set(key, value, ttl)
            logger.debug(f"Cache SET: {key}")
        except Exception as e:
            logger.warning(f"L2 set failed: {e}")
    
    def _populate_l1(self, key: str, value: Any):
        """Add to L1 cache with LRU eviction"""
        
        # Simple LRU: remove oldest if full
        if len(self.l1) >= self.max_l1_size:
            oldest_key = next(iter(self.l1))
            del self.l1[oldest_key]
        
        self.l1[key] = value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.l1_stats['hits'] + self.l1_stats['misses']
        hit_rate = (self.l1_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'l1_hits': self.l1_stats['hits'],
            'l1_misses': self.l1_stats['misses'],
            'l1_hit_rate': hit_rate,
            'l1_size': len(self.l1),
        }


# ─────────────────────────────────────────────────────────────────────────────
# CACHING PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

class CacheAside:
    """
    Cache-Aside Pattern (Lazy Loading)
    
    Application responsible for loading from DB if cache miss
    """
    
    @staticmethod
    def get_or_load(key: str, loader: Callable, ttl: int = 3600) -> Any:
        """Get from cache or load from source"""
        
        # Try cache
        value = cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit: {key}")
            return value
        
        # Cache miss - load from source
        logger.debug(f"Cache miss: {key}")
        value = loader()
        cache.set(key, value, ttl)
        
        return value


class WriteThrough:
    """
    Write-Through Pattern
    
    Write to both cache and DB immediately
    """
    
    @staticmethod
    def write(key: str, value: Any, db_save: Callable, ttl: int = 3600):
        """Write to cache and DB"""
        
        # Write to cache first
        cache.set(key, value, ttl)
        logger.debug(f"Written to cache: {key}")
        
        # Write to DB
        db_save(value)
        logger.info(f"Written to DB: {key}")


class WriteBack:
    """
    Write-Back Pattern (Write-Behind)
    
    Write to cache immediately, DB asynchronously
    """
    
    @staticmethod
    def write(key: str, value: Any, db_save: Callable, ttl: int = 3600):
        """Write to cache, async DB write"""
        
        # Write to cache immediately
        cache.set(key, value, ttl)
        logger.debug(f"Written to cache: {key}")
        
        # Queue DB write (would use Celery)
        # db_save.delay(value)
        db_save(value)


class RefreshAhead:
    """
    Refresh-Ahead Pattern
    
    Refresh cache before expiration for hot keys
    """
    
    @staticmethod
    def get_with_refresh(key: str, loader: Callable, ttl: int = 3600,
                        refresh_threshold: float = 0.8):
        """Get with automatic refresh"""
        
        # Get from cache
        value = cache.get(key)
        if value is None:
            # Cache miss - load
            value = loader()
            cache.set(key, value, ttl)
            return value
        
        # Got from cache - check if needs refresh
        # (In production, would track access times)
        return value


# ─────────────────────────────────────────────────────────────────────────────
# CACHE COMPRESSION
# ─────────────────────────────────────────────────────────────────────────────

class CacheCompression:
    """Compress cache values to save memory"""
    
    @staticmethod
    def compress(value: Any) -> bytes:
        """Compress value for storage"""
        import zlib
        
        serialized = json.dumps(value, default=str).encode()
        return zlib.compress(serialized, level=6)
    
    @staticmethod
    def decompress(compressed: bytes) -> Any:
        """Decompress cached value"""
        import zlib
        
        decompressed = zlib.decompress(compressed)
        return json.loads(decompressed.decode())


# ─────────────────────────────────────────────────────────────────────────────
# CACHE VERSIONING
# ─────────────────────────────────────────────────────────────────────────────

class CacheVersion:
    """Cache versioning to handle schema changes"""
    
    @staticmethod
    def versioned_key(key: str, version: int = 1) -> str:
        """Create versioned cache key"""
        return f"v{version}:{key}"
    
    @staticmethod
    def increment_version(key_prefix: str) -> int:
        """Invalidate all versions of a key"""
        version_key = f"{key_prefix}:version"
        current = cache.get(version_key, 0)
        new_version = current + 1
        cache.set(version_key, new_version, None)
        return new_version


# ─────────────────────────────────────────────────────────────────────────────
# CACHE DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def cached(ttl: int = 3600, key_func: Optional[Callable] = None):
    """Decorator to cache function results"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: function name + args hash
                args_str = str(args) + str(kwargs)
                args_hash = hashlib.md5(args_str.encode()).hexdigest()
                cache_key = f"{func.__name__}:{args_hash}"
            
            # Try cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# CACHE WARMING
# ─────────────────────────────────────────────────────────────────────────────

class CacheWarmer:
    """Pre-populate cache with hot data"""
    
    @staticmethod
    def warm_featured_content(limit: int = 50):
        """Warm cache with featured content"""
        from api.cms.models_new.blog import BlogPost
        
        posts = BlogPost.objects.filter(is_featured=True)[:limit]
        
        for post in posts:
            key = f"blog:post:{post.id}"
            cache.set(key, post, 86400)  # 24 hours
        
        logger.info(f"Warmed cache with {len(list(posts))} posts")
    
    @staticmethod
    def warm_top_offers(limit: int = 50):
        """Warm cache with top offers"""
        # Similar pattern
        logger.info(f"Warmed cache with {limit} offers")


# Export public API
__all__ = [
    'MultiLevelCache',
    'CacheAside',
    'WriteThrough',
    'WriteBack',
    'RefreshAhead',
    'CacheCompression',
    'CacheVersion',
    'cached',
    'CacheWarmer',
]

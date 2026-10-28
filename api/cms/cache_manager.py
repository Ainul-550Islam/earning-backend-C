# cms/cache_manager.py
"""
Cache Management System for CMS

Centralized cache handling with:
- Cache key patterns and namespacing
- Automatic invalidation on model changes
- Cache warming strategies
- Monitoring and debugging
- Multi-level caching (Redis, memory)

Key Features:
1. Namespaced cache keys (cache_blog:post:123)
2. Automatic invalidation via signals
3. Batch invalidation support
4. Cache statistics and monitoring
5. Debug mode for development
6. TTL management per cache type
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from functools import wraps
from datetime import timedelta
import json
import logging
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('cms.cache')


# ─────────────────────────────────────────────────────────────────────────────
# CACHE KEY DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

class CacheKeys:
    """
    Centralized cache key definitions
    
    Ensures consistency across the application.
    Format: {namespace}:{resource}:{id}
    """
    
    # TTLs (Time To Live)
    TTL_SHORT = 300  # 5 minutes
    TTL_MEDIUM = 3600  # 1 hour
    TTL_LONG = 86400  # 24 hours
    
    # Blog
    BLOG_POST = 'blog:post:{id}'
    BLOG_CATEGORY = 'blog:category:{id}'
    BLOG_POSTS_BY_CATEGORY = 'blog:posts_by_category:{category_id}'
    BLOG_FEATURED_POSTS = 'blog:featured_posts'
    BLOG_RECENT_POSTS = 'blog:recent_posts'
    
    # Survey
    SURVEY = 'survey:{id}'
    SURVEY_COMPLETION = 'survey:completion:{id}'
    SURVEY_STATS = 'survey:stats:{id}'
    
    # Quiz
    QUIZ = 'quiz:{id}'
    QUIZ_ATTEMPT = 'quiz:attempt:{id}'
    
    # Offers
    OFFER = 'offer:{id}'
    OFFERWALL = 'offerwall:{id}'
    USER_OFFERS = 'user:offers:{user_id}'
    ACTIVE_OFFERS = 'offers:active'
    
    # Leaderboard
    LEADERBOARD = 'leaderboard:{id}'
    USER_RANK = 'user:rank:{user_id}'
    TOP_EARNERS = 'leaderboard:top_earners'
    
    # User
    USER_PROFILE = 'user:profile:{id}'
    USER_BALANCE = 'user:balance:{id}'
    USER_WALLET = 'user:wallet:{id}'
    
    # CMS
    PAGE = 'cms:page:{id}'
    BANNER = 'cms:banner:{id}'
    MENU = 'cms:menu:{id}'
    
    # Analytics
    DAILY_STATS = 'analytics:daily_stats:{date}'
    USER_STATS = 'analytics:user_stats:{user_id}'

    @staticmethod
    def pattern_for_prefix(prefix: str) -> str:
        """Get cache key pattern for prefix (for mass deletion)"""
        return f"{prefix}:*"


# ─────────────────────────────────────────────────────────────────────────────
# CACHE MANAGER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class CacheManager:
    """
    Central cache manager with intelligent invalidation and warming
    
    Usage:
        cache_mgr = CacheManager()
        
        # Get with auto-population
        data = cache_mgr.get_or_set('blog:post:1', 
                                     lambda: BlogPost.objects.get(id=1),
                                     ttl=3600)
        
        # Invalidate on update
        cache_mgr.invalidate('blog:post:1')
        
        # Batch invalidate
        cache_mgr.invalidate_pattern('blog:posts_by_category:*')
        
        # Get stats
        stats = cache_mgr.get_stats()
    """
    
    # Track invalidations for debugging
    _invalidation_log = []
    _max_log_size = 1000
    
    def __init__(self, backend: str = 'default'):
        """
        Initialize cache manager
        
        Args:
            backend: Cache backend name ('default' or custom)
        """
        self.backend = backend
        self.cache = cache
        self.enabled = getattr(settings, 'CACHE_ENABLED', True)
        self.debug_mode = getattr(settings, 'CACHE_DEBUG', False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # BASIC OPERATIONS
    # ─────────────────────────────────────────────────────────────────────────
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
        
        try:
            value = self.cache.get(key)
            if self.debug_mode:
                logger.debug(f"Cache GET {key}: {'HIT' if value else 'MISS'}")
            return value
        except Exception as e:
            logger.error(f"Cache GET error for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        if not self.enabled:
            return False
        
        ttl = ttl or CacheKeys.TTL_MEDIUM
        
        try:
            self.cache.set(key, value, ttl)
            if self.debug_mode:
                logger.debug(f"Cache SET {key} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Cache SET error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.enabled:
            return False
        
        try:
            self.cache.delete(key)
            if self.debug_mode:
                logger.debug(f"Cache DELETE {key}")
            return True
        except Exception as e:
            logger.error(f"Cache DELETE error for {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        return self.get(key) is not None
    
    def clear(self) -> bool:
        """Clear all cache"""
        if not self.enabled:
            return False
        
        try:
            self.cache.clear()
            logger.warning("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────────
    # ADVANCED OPERATIONS
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_or_set(self, 
                   key: str, 
                   callable_fn: Callable,
                   ttl: int = None) -> Any:
        """
        Get from cache or execute callable and cache result
        
        Args:
            key: Cache key
            callable_fn: Function to execute if cache miss
            ttl: Time to live in seconds
            
        Returns:
            Cached or freshly computed value
        """
        # Try cache first
        value = self.get(key)
        if value is not None:
            if self.debug_mode:
                logger.debug(f"Cache HIT for {key}")
            return value
        
        # Cache miss - compute value
        if self.debug_mode:
            logger.debug(f"Cache MISS for {key}, executing callable")
        
        try:
            value = callable_fn()
            self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"Error computing cache value for {key}: {e}")
            return None
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        if not self.enabled:
            return {}
        
        try:
            return self.cache.get_many(keys)
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}
    
    def set_many(self, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple values in cache"""
        if not self.enabled:
            return False
        
        ttl = ttl or CacheKeys.TTL_MEDIUM
        
        try:
            self.cache.set_many(data, ttl)
            if self.debug_mode:
                logger.debug(f"Cache SET_MANY {len(data)} keys")
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False
    
    def delete_many(self, keys: List[str]) -> bool:
        """Delete multiple keys from cache"""
        if not self.enabled:
            return False
        
        try:
            self.cache.delete_many(keys)
            if self.debug_mode:
                logger.debug(f"Cache DELETE_MANY {len(keys)} keys")
            return True
        except Exception as e:
            logger.error(f"Cache delete_many error: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────────
    # INVALIDATION
    # ─────────────────────────────────────────────────────────────────────────
    
    def invalidate(self, key: str) -> bool:
        """
        Invalidate cache key
        
        Log invalidation for debugging
        """
        self._log_invalidation(key)
        return self.delete(key)
    
    def invalidate_many(self, keys: List[str]) -> int:
        """Invalidate multiple keys"""
        deleted = 0
        for key in keys:
            if self.delete(key):
                deleted += 1
                self._log_invalidation(key)
        
        return deleted
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern
        
        Pattern uses wildcards: blog:post:*
        Note: Some backends don't support pattern matching
        """
        try:
            # Try to get all keys (implementation depends on backend)
            # This is a simplified version - real implementation needs backend support
            keys_to_delete = self._find_keys_by_pattern(pattern)
            deleted = self.delete_many(keys_to_delete)
            
            for key in keys_to_delete:
                self._log_invalidation(key)
            
            logger.info(f"Invalidated {len(keys_to_delete)} keys matching {pattern}")
            return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Pattern invalidation failed for {pattern}: {e}")
            return 0
    
    def _find_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Find keys matching pattern
        
        Note: Implementation depends on cache backend
        Redis: Can use KEYS command
        Memcached: Difficult - may need key tracking
        """
        # For Redis backend
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection('default')
            
            # Convert pattern to Redis format
            pattern_key = pattern.replace(':', ':').encode()
            keys = redis_conn.keys(pattern_key)
            return [k.decode() for k in keys]
        except Exception as e:
            logger.warning(f"Could not find keys by pattern (backend doesn't support): {e}")
            return []
    
    def _log_invalidation(self, key: str):
        """Log cache invalidation for debugging"""
        self._invalidation_log.append({
            'key': key,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Keep log size bounded
        if len(self._invalidation_log) > self._max_log_size:
            self._invalidation_log = self._invalidation_log[-self._max_log_size:]
        
        if self.debug_mode:
            logger.debug(f"Cache INVALIDATE {key}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # WARMING (PRE-CACHING)
    # ─────────────────────────────────────────────────────────────────────────
    
    def warm_featured_posts(self) -> int:
        """Pre-cache featured blog posts"""
        try:
            from api.cms.models_new.blog import BlogPost
            
            posts = BlogPost.objects.filter(
                is_featured=True,
                is_published=True
            )[:20]
            
            from api.cms.serializers_new.BlogAndSEOSerializer import BlogPostListSerializer
            serializer = BlogPostListSerializer(posts, many=True)
            
            self.set(
                CacheKeys.BLOG_FEATURED_POSTS,
                serializer.data,
                ttl=CacheKeys.TTL_LONG
            )
            
            logger.info(f"Warmed cache for {len(posts)} featured posts")
            return len(posts)
        except Exception as e:
            logger.error(f"Failed to warm featured posts: {e}")
            return 0
    
    def warm_recent_posts(self) -> int:
        """Pre-cache recent blog posts"""
        try:
            from api.cms.models_new.blog import BlogPost
            
            posts = BlogPost.objects.filter(
                is_published=True
            ).order_by('-published_at')[:20]
            
            from api.cms.serializers_new.BlogAndSEOSerializer import BlogPostListSerializer
            serializer = BlogPostListSerializer(posts, many=True)
            
            self.set(
                CacheKeys.BLOG_RECENT_POSTS,
                serializer.data,
                ttl=CacheKeys.TTL_MEDIUM
            )
            
            logger.info(f"Warmed cache for {len(posts)} recent posts")
            return len(posts)
        except Exception as e:
            logger.error(f"Failed to warm recent posts: {e}")
            return 0
    
    def warm_active_offers(self) -> int:
        """Pre-cache active offers"""
        try:
            from api.cms.models_new.cpalead import Offer
            
            offers = Offer.objects.filter(is_active=True)[:50]
            
            from api.cms.serializers_new.OfferwallSerializer import OfferSerializer
            serializer = OfferSerializer(offers, many=True)
            
            self.set(
                CacheKeys.ACTIVE_OFFERS,
                serializer.data,
                ttl=CacheKeys.TTL_SHORT
            )
            
            logger.info(f"Warmed cache for {len(offers)} active offers")
            return len(offers)
        except Exception as e:
            logger.error(f"Failed to warm active offers: {e}")
            return 0
    
    def warm_leaderboard(self, top_n: int = 100) -> int:
        """Pre-cache top leaderboard"""
        try:
            from api.cms.models_new.leaderboard import Leaderboard
            
            leaderboard = Leaderboard.objects.filter(
                is_active=True
            ).order_by('-total_points')[:top_n]
            
            from api.cms.serializers_new.LeaderboardSerializer import LeaderboardSerializer
            serializer = LeaderboardSerializer(leaderboard, many=True)
            
            self.set(
                CacheKeys.TOP_EARNERS,
                serializer.data,
                ttl=CacheKeys.TTL_MEDIUM
            )
            
            logger.info(f"Warmed cache for top {len(leaderboard)} earners")
            return len(leaderboard)
        except Exception as e:
            logger.error(f"Failed to warm leaderboard: {e}")
            return 0
    
    def warm_all(self) -> int:
        """Warm all critical caches"""
        count = 0
        count += self.warm_featured_posts()
        count += self.warm_recent_posts()
        count += self.warm_active_offers()
        count += self.warm_leaderboard()
        
        logger.info(f"✓ Cache warming complete: {count} items cached")
        return count
    
    # ─────────────────────────────────────────────────────────────────────────
    # MONITORING & STATISTICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # Try to get stats from backend
            stats = self.cache._cache.get_stats() if hasattr(self.cache, '_cache') else {}
            
            return {
                'enabled': self.enabled,
                'debug_mode': self.debug_mode,
                'backend': self.backend,
                'recent_invalidations': len(self._invalidation_log),
                'stats': stats,
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'error': str(e)}
    
    def get_invalidation_log(self, limit: int = 100) -> List[Dict]:
        """Get recent cache invalidations"""
        return self._invalidation_log[-limit:]
    
    def clear_invalidation_log(self):
        """Clear invalidation log"""
        self._invalidation_log = []
    
    # ─────────────────────────────────────────────────────────────────────────
    # DECORATORS
    # ─────────────────────────────────────────────────────────────────────────
    
    def cache_result(self, key: str, ttl: int = None):
        """
        Decorator to cache function result
        
        Usage:
            @cache_manager.cache_result('user:profile:{user_id}', ttl=3600)
            def get_user_profile(user_id):
                return UserProfile.objects.get(id=user_id)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Resolve key with arguments
                resolved_key = key.format(
                    *args,
                    **kwargs
                ) if '{' in key else key
                
                # Try cache
                cached = self.get(resolved_key)
                if cached is not None:
                    return cached
                
                # Compute and cache
                result = func(*args, **kwargs)
                self.set(resolved_key, result, ttl)
                return result
            
            return wrapper
        
        return decorator


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

# Global cache manager instance
cache_manager = CacheManager()


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def invalidate_cache_on_save(model_class):
    """
    Decorator for signal handlers to invalidate cache on model save
    
    Usage:
        @invalidate_cache_on_save(BlogPost)
        def my_signal_handler(sender, instance, **kwargs):
            # Auto-invalidate blog post cache
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(sender, instance, **kwargs):
            # Call original handler
            result = func(sender, instance, **kwargs)
            
            # Invalidate cache
            cache_key = f'cache_{model_class.__name__}:{instance.id}'
            cache_manager.invalidate(cache_key)
            
            return result
        
        return wrapper
    
    return decorator


def warm_critical_caches():
    """Warm critical caches on application startup"""
    logger.info("Starting cache warming...")
    cache_manager.warm_all()
    logger.info("✓ Cache warming complete")


# ─────────────────────────────────────────────────────────────────────────────
# MANAGEMENT COMMAND SUPPORT
# ─────────────────────────────────────────────────────────────────────────────

class CacheManagementCommand:
    """
    Management command for cache operations
    
    Usage:
        python manage.py cms_cache --action=warm
        python manage.py cms_cache --action=clear
        python manage.py cms_cache --action=stats
    """
    
    @staticmethod
    def warm():
        """Warm all caches"""
        count = cache_manager.warm_all()
        print(f"✓ Warmed {count} cache entries")
    
    @staticmethod
    def clear():
        """Clear all caches"""
        cache_manager.clear()
        print("✓ Cache cleared")
    
    @staticmethod
    def stats():
        """Show cache statistics"""
        stats = cache_manager.get_stats()
        print(json.dumps(stats, indent=2))
    
    @staticmethod
    def invalidate_pattern(pattern: str):
        """Invalidate keys matching pattern"""
        count = cache_manager.invalidate_pattern(pattern)
        print(f"✓ Invalidated {count} keys matching {pattern}")


# Export public API
__all__ = [
    'CacheKeys',
    'CacheManager',
    'cache_manager',
    'invalidate_cache_on_save',
    'warm_critical_caches',
    'CacheManagementCommand',
]

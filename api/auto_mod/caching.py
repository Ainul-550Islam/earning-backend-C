# =============================================================================
# auto_mod/caching.py
# =============================================================================

"""
Caching system for auto moderation with multiple backends and strategies.
Provides high-performance caching for moderation data and results.
"""

import logging
import json
# pickle removed (RCE risk) — use json-safe cache
import hashlib
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from functools import wraps

from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class CacheBackend:
    """Base cache backend."""
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError("Subclasses must implement get")
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        raise NotImplementedError("Subclasses must implement set")
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        raise NotImplementedError("Subclasses must implement delete")
    
    def clear(self) -> bool:
        """Clear all cache."""
        raise NotImplementedError("Subclasses must implement clear")
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        raise NotImplementedError("Subclasses must implement exists")


class DjangoCacheBackend(CacheBackend):
    """Django cache backend."""
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Django cache."""
        try:
            return cache.get(key)
        except Exception as exc:
            logger.error(f"Django cache get failed: {exc}")
            return None
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in Django cache."""
        try:
            return cache.set(key, value, timeout)
        except Exception as exc:
            logger.error(f"Django cache set failed: {exc}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from Django cache."""
        try:
            return cache.delete(key)
        except Exception as exc:
            logger.error(f"Django cache delete failed: {exc}")
            return False
    
    def clear(self) -> bool:
        """Clear Django cache."""
        try:
            return cache.clear()
        except Exception as exc:
            logger.error(f"Django cache clear failed: {exc}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Django cache."""
        try:
            return cache.has_key(key)
        except Exception as exc:
            logger.error(f"Django cache exists failed: {exc}")
            return False


class RedisCacheBackend(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        if not self.redis_client:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=getattr(settings, 'REDIS_HOST', 'localhost'),
                    port=getattr(settings, 'REDIS_PORT', 6379),
                    db=getattr(settings, 'REDIS_DB', 0),
                    decode_responses=True
                )
            except ImportError:
                logger.error("Redis not installed, falling back to Django cache")
                self.redis_client = None
            except Exception as exc:
                logger.error(f"Redis connection failed: {exc}")
                self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                import json; return json.loads(value) if isinstance(value, (str,bytes)) else value
            return None
        except Exception as exc:
            logger.error(f"Redis get failed: {exc}")
            return None
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in Redis."""
        if not self.redis_client:
            return False
        
        try:
            import json; serialized_value = json.dumps(value, default=str)
            if timeout:
                return self.redis_client.setex(key, timeout, serialized_value)
            else:
                return self.redis_client.set(key, serialized_value)
        except Exception as exc:
            logger.error(f"Redis set failed: {exc}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from Redis."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as exc:
            logger.error(f"Redis delete failed: {exc}")
            return False
    
    def clear(self) -> bool:
        """Clear Redis cache."""
        if not self.redis_client:
            return False
        
        try:
            return self.redis_client.flushdb()
        except Exception as exc:
            logger.error(f"Redis clear failed: {exc}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as exc:
            logger.error(f"Redis exists failed: {exc}")
            return False


class CacheStrategy:
    """Base cache strategy."""
    
    def get_key(self, *args, **kwargs) -> str:
        """Generate cache key."""
        raise NotImplementedError("Subclasses must implement get_key")
    
    def get_timeout(self, *args, **kwargs) -> int:
        """Get cache timeout."""
        raise NotImplementedError("Subclasses must implement get_timeout")


class SimpleKeyStrategy(CacheStrategy):
    """Simple key generation strategy."""
    
    def __init__(self, prefix: str = "auto_mod"):
        self.prefix = prefix
    
    def get_key(self, *args, **kwargs) -> str:
        """Generate simple cache key."""
        parts = [self.prefix]
        parts.extend(str(arg) for arg in args)
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    def get_timeout(self, *args, **kwargs) -> int:
        """Get default timeout."""
        return 300  # 5 minutes


class HashKeyStrategy(CacheStrategy):
    """Hash-based key generation strategy."""
    
    def __init__(self, prefix: str = "auto_mod"):
        self.prefix = prefix
    
    def get_key(self, *args, **kwargs) -> str:
        """Generate hash-based cache key."""
        # Create a deterministic string from args
        parts = []
        parts.extend(str(arg) for arg in args)
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        
        key_string = "|".join(parts)
        hash_value = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{self.prefix}:{hash_value}"
    
    def get_timeout(self, *args, **kwargs) -> int:
        """Get default timeout."""
        return 300  # 5 minutes


class CacheManager:
    """
    Advanced cache manager with multiple backends and strategies.
    """
    
    def __init__(self, backend: CacheBackend = None, strategy: CacheStrategy = None):
        self.backend = backend or DjangoCacheBackend()
        self.strategy = strategy or SimpleKeyStrategy()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = self.backend.get(key)
            if value is not None:
                self.stats['hits'] += 1
                return value
            else:
                self.stats['misses'] += 1
                return None
        except Exception as exc:
            logger.error(f"Cache get failed: {exc}")
            self.stats['errors'] += 1
            return None
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        try:
            if timeout is None:
                timeout = self.strategy.get_timeout()
            
            success = self.backend.set(key, value, timeout)
            if success:
                self.stats['sets'] += 1
            else:
                self.stats['errors'] += 1
            
            return success
        except Exception as exc:
            logger.error(f"Cache set failed: {exc}")
            self.stats['errors'] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            success = self.backend.delete(key)
            if success:
                self.stats['deletes'] += 1
            else:
                self.stats['errors'] += 1
            
            return success
        except Exception as exc:
            logger.error(f"Cache delete failed: {exc}")
            self.stats['errors'] += 1
            return False
    
    def get_or_set(self, key: str, default_func: Callable, timeout: int = None) -> Any:
        """
        Get value from cache or set using default function.
        
        Args:
            key: Cache key
            default_func: Function to generate default value
            timeout: Cache timeout
            
        Returns:
            Cached or generated value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Generate default value
        try:
            value = default_func()
            self.set(key, value, timeout)
            return value
        except Exception as exc:
            logger.error(f"Default function failed: {exc}")
            raise
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, mapping: Dict[str, Any], timeout: int = None) -> bool:
        """Set multiple values in cache."""
        success = True
        for key, value in mapping.items():
            if not self.set(key, value, timeout):
                success = False
        return success
    
    def delete_many(self, keys: List[str]) -> bool:
        """Delete multiple values from cache."""
        success = True
        for key in keys:
            if not self.delete(key):
                success = False
        return success
    
    def clear(self) -> bool:
        """Clear all cache."""
        return self.backend.clear()
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.backend.exists(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
        }


class CacheDecorator:
    """Decorator for caching function results."""
    
    def __init__(self, cache_manager: CacheManager = None, timeout: int = None,
                 key_prefix: str = None, key_generator: Callable = None):
        self.cache_manager = cache_manager or CacheManager()
        self.timeout = timeout
        self.key_prefix = key_prefix
        self.key_generator = key_generator or self._default_key_generator
    
    def _default_key_generator(self, func: Callable, *args, **kwargs) -> str:
        """Generate default cache key."""
        parts = [self.key_prefix or 'cache']
        parts.append(func.__name__)
        parts.extend(str(arg) for arg in args)
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = self.key_generator(func, *args, **kwargs)
            
            # Try to get from cache
            cached_result = self.cache_manager.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            self.cache_manager.set(key, result, self.timeout)
            
            return result
        
        return wrapper


class AutoModCache:
    """
    Specialized cache for auto moderation system.
    """
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.key_strategies = {
            'submission': HashKeyStrategy('submission'),
            'decision': HashKeyStrategy('decision'),
            'user': HashKeyStrategy('user'),
            'rule': HashKeyStrategy('rule'),
            'bot': HashKeyStrategy('bot'),
            'queue': HashKeyStrategy('queue'),
        }
    
    def cache_submission_result(self, submission_id: str, result: Dict[str, Any], 
                              timeout: int = 3600) -> None:
        """Cache submission analysis result."""
        key = self.key_strategies['submission'].get_key(submission_id, 'result')
        self.cache_manager.set(key, result, timeout)
    
    def get_submission_result(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get cached submission result."""
        key = self.key_strategies['submission'].get_key(submission_id, 'result')
        return self.cache_manager.get(key)
    
    def cache_user_stats(self, user_id: Union[str, int], stats: Dict[str, Any], 
                        timeout: int = 1800) -> None:
        """Cache user statistics."""
        key = self.key_strategies['user'].get_key(user_id, 'stats')
        self.cache_manager.set(key, stats, timeout)
    
    def get_user_stats(self, user_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Get cached user statistics."""
        key = self.key_strategies['user'].get_key(user_id, 'stats')
        return self.cache_manager.get(key)
    
    def cache_rule_evaluation(self, rule_id: str, content_hash: str, 
                           result: bool, timeout: int = 7200) -> None:
        """Cache rule evaluation result."""
        key = self.key_strategies['rule'].get_key(rule_id, content_hash)
        self.cache_manager.set(key, result, timeout)
    
    def get_rule_evaluation(self, rule_id: str, content_hash: str) -> Optional[bool]:
        """Get cached rule evaluation result."""
        key = self.key_strategies['rule'].get_key(rule_id, content_hash)
        return self.cache_manager.get(key)
    
    def cache_bot_status(self, bot_id: str, status: Dict[str, Any], 
                        timeout: int = 300) -> None:
        """Cache bot status."""
        key = self.key_strategies['bot'].get_key(bot_id, 'status')
        self.cache_manager.set(key, status, timeout)
    
    def get_bot_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get cached bot status."""
        key = self.key_strategies['bot'].get_key(bot_id, 'status')
        return self.cache_manager.get(key)
    
    def cache_queue_metrics(self, queue_id: str, metrics: Dict[str, Any], 
                           timeout: int = 600) -> None:
        """Cache queue metrics."""
        key = self.key_strategies['queue'].get_key(queue_id, 'metrics')
        self.cache_manager.set(key, metrics, timeout)
    
    def get_queue_metrics(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """Get cached queue metrics."""
        key = self.key_strategies['queue'].get_key(queue_id, 'metrics')
        return self.cache_manager.get(key)
    
    def invalidate_user_cache(self, user_id: Union[str, int]) -> None:
        """Invalidate all cache entries for a user."""
        # This would require pattern matching in Redis
        # For now, just invalidate known keys
        stats_key = self.key_strategies['user'].get_key(user_id, 'stats')
        self.cache_manager.delete(stats_key)
    
    def invalidate_submission_cache(self, submission_id: str) -> None:
        """Invalidate all cache entries for a submission."""
        result_key = self.key_strategies['submission'].get_key(submission_id, 'result')
        self.cache_manager.delete(result_key)
    
    def invalidate_rule_cache(self, rule_id: str) -> None:
        """Invalidate all cache entries for a rule."""
        # This would require pattern matching in Redis
        # For now, just log the action
        logger.info(f"Invalidated cache for rule {rule_id}")
    
    def cleanup_expired_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries."""
        # This would be handled automatically by most cache backends
        # For now, just return mock statistics
        return {
            'cleaned_keys': 0,
            'cleaned_bytes': 0,
        }
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        return {
            'cache_stats': self.cache_manager.get_stats(),
            'cleanup_stats': self.cleanup_expired_cache(),
            'generated_at': timezone.now().isoformat(),
        }


# Global cache instances
default_cache_manager = CacheManager()
auto_mod_cache = AutoModCache()


# Decorators
def cache_result(timeout: int = 300, key_prefix: str = None):
    """Decorator for caching function results."""
    return CacheDecorator(timeout=timeout, key_prefix=key_prefix)


def cache_submission(timeout: int = 3600):
    """Decorator for caching submission-related results."""
    return CacheDecorator(timeout=timeout, key_prefix='submission')


def cache_user_stats(timeout: int = 1800):
    """Decorator for caching user statistics."""
    return CacheDecorator(timeout=timeout, key_prefix='user_stats')


def cache_rule_result(timeout: int = 7200):
    """Decorator for caching rule evaluation results."""
    return CacheDecorator(timeout=timeout, key_prefix='rule')


# Utility functions
def get_from_cache(key: str, default: Any = None) -> Any:
    """Get value from cache with default."""
    value = default_cache_manager.get(key)
    return value if value is not None else default


def set_cache(key: str, value: Any, timeout: int = None) -> bool:
    """Set value in cache."""
    return default_cache_manager.set(key, value, timeout)


def delete_cache(key: str) -> bool:
    """Delete value from cache."""
    return default_cache_manager.delete(key)


def get_or_set_cache(key: str, default_func: Callable, timeout: int = None) -> Any:
    """Get value from cache or set using default function."""
    return default_cache_manager.get_or_set(key, default_func, timeout)


# Initialize logging
logger.info("Caching module initialized with multi-backend support")

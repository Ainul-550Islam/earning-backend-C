"""
Cache Management for Advertiser Portal

This module provides caching utilities and cache management
for improving application performance and reducing database load.
"""

import json
import pickle
import hashlib
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db.models import Model
from django.core.serializers.json import DjangoJSONEncoder

from .constants import CacheConstants
from .utils import CacheUtils
from .exceptions import CacheError


class CacheManager:
    """Advanced cache manager with multiple backends and strategies."""
    
    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or getattr(settings, 'CACHE_BACKEND', 'default')
        self.default_timeout = getattr(settings, 'CACHE_DEFAULT_TIMEOUT', 300)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            
            # Log cache hit/miss for monitoring
            if value is not None:
                self._log_cache_event('hit', key)
            else:
                self._log_cache_event('miss', key)
            
            return value
            
        except Exception as e:
            self._log_cache_error('get', key, e)
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful
        """
        try:
            timeout = timeout or self.default_timeout
            
            # Serialize complex objects
            if self._needs_serialization(value):
                value = self._serialize(value)
            
            result = cache.set(key, value, timeout)
            
            if result:
                self._log_cache_event('set', key, timeout)
            
            return result
            
        except Exception as e:
            self._log_cache_error('set', key, e)
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        try:
            result = cache.delete(key)
            
            if result:
                self._log_cache_event('delete', key)
            
            return result
            
        except Exception as e:
            self._log_cache_error('delete', key, e)
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs
        """
        try:
            result = cache.get_many(keys)
            
            # Log cache hits/misses
            for key in keys:
                if key in result:
                    self._log_cache_event('hit', key)
                else:
                    self._log_cache_event('miss', key)
            
            # Deserialize values if needed
            for key, value in result.items():
                if self._is_serialized(value):
                    result[key] = self._deserialize(value)
            
            return result
            
        except Exception as e:
            self._log_cache_error('get_many', str(keys), e)
            return {}
    
    def set_many(self, data: Dict[str, Any], timeout: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            data: Dictionary of key-value pairs
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful
        """
        try:
            timeout = timeout or self.default_timeout
            
            # Serialize values if needed
            serialized_data = {}
            for key, value in data.items():
                if self._needs_serialization(value):
                    serialized_data[key] = self._serialize(value)
                else:
                    serialized_data[key] = value
            
            result = cache.set_many(serialized_data, timeout)
            
            if result:
                self._log_cache_event('set_many', list(data.keys()), timeout)
            
            return result
            
        except Exception as e:
            self._log_cache_error('set_many', str(data.keys()), e)
            return False
    
    def delete_many(self, keys: List[str]) -> bool:
        """
        Delete multiple keys from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            True if successful
        """
        try:
            result = cache.delete_many(keys)
            
            if result:
                self._log_cache_event('delete_many', keys)
            
            return result
            
        except Exception as e:
            self._log_cache_error('delete_many', str(keys), e)
            return False
    
    def incr(self, key: str, delta: int = 1) -> Optional[int]:
        """
        Increment numeric value in cache.
        
        Args:
            key: Cache key
            delta: Increment amount
            
        Returns:
            New value or None
        """
        try:
            result = cache.incr(key, delta)
            
            if result is not None:
                self._log_cache_event('incr', key, delta)
            
            return result
            
        except Exception as e:
            self._log_cache_error('incr', key, e)
            return None
    
    def decr(self, key: str, delta: int = 1) -> Optional[int]:
        """
        Decrement numeric value in cache.
        
        Args:
            key: Cache key
            delta: Decrement amount
            
        Returns:
            New value or None
        """
        try:
            result = cache.decr(key, delta)
            
            if result is not None:
                self._log_cache_event('decr', key, delta)
            
            return result
            
        except Exception as e:
            self._log_cache_error('decr', key, e)
            return None
    
    def touch(self, key: str, timeout: Optional[int] = None) -> bool:
        """
        Update timeout for existing key.
        
        Args:
            key: Cache key
            timeout: New timeout in seconds
            
        Returns:
            True if successful
        """
        try:
            timeout = timeout or self.default_timeout
            
            # Get current value
            value = cache.get(key)
            if value is None:
                return False
            
            # Set new timeout
            result = cache.set(key, value, timeout)
            
            if result:
                self._log_cache_event('touch', key, timeout)
            
            return result
            
        except Exception as e:
            self._log_cache_error('touch', key, e)
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        try:
            result = cache.get(key) is not None
            self._log_cache_event('exists', key)
            return result
            
        except Exception as e:
            self._log_cache_error('exists', key, e)
            return False
    
    def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful
        """
        try:
            result = cache.clear()
            self._log_cache_event('clear', 'all')
            return result
            
        except Exception as e:
            self._log_cache_error('clear', 'all', e)
            return False
    
    def _needs_serialization(self, value: Any) -> bool:
        """Check if value needs serialization."""
        # Simple types don't need serialization
        if isinstance(value, (str, int, float, bool, type(None))):
            return False
        
        # Django models and complex objects need serialization
        if isinstance(value, (dict, list, tuple, set)):
            return True
        
        if isinstance(value, (datetime, Decimal)):
            return True
        
        if hasattr(value, '_meta'):  # Django model
            return True
        
        return False
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for caching."""
        if isinstance(value, Model):
            # Serialize Django model
            return json.dumps({
                'model': value.__class__.__name__,
                'pk': value.pk,
                'data': {field.name: getattr(value, field.name) for field in value._meta.fields}
            }, cls=DjangoJSONEncoder)
        
        # Use JSON for other complex types
        return json.dumps(value, cls=DjangoJSONEncoder)
    
    def _is_serialized(self, value: Any) -> bool:
        """Check if value is serialized."""
        return isinstance(value, str) and value.startswith('{"model":')
    
    def _deserialize(self, value: str) -> Any:
        """Deserialize cached value."""
        try:
            data = json.loads(value)
            
            # Handle Django model serialization
            if isinstance(data, dict) and 'model' in data and 'data' in data:
                # This would need to be implemented based on your model structure
                # For now, return the data dictionary
                return data['data']
            
            return data
            
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _log_cache_event(self, operation: str, key: Union[str, List[str]], 
                         extra: Any = None) -> None:
        """Log cache operation for monitoring."""
        import logging
        
        logger = logging.getLogger('cache.operations')
        
        log_data = {
            'operation': operation,
            'key': key,
            'timestamp': timezone.now().isoformat(),
        }
        
        if extra is not None:
            log_data['extra'] = extra
        
        logger.debug(f"Cache operation: {log_data}")
    
    def _log_cache_error(self, operation: str, key: str, error: Exception) -> None:
        """Log cache error."""
        import logging
        
        logger = logging.getLogger('cache.errors')
        
        logger.error(
            f"Cache error in {operation} for key {key}: {str(error)}",
            exc_info=True
        )


class CacheKeyBuilder:
    """Utility class for building cache keys."""
    
    @staticmethod
    def build_key(prefix: str, *args, **kwargs) -> str:
        """
        Build cache key from prefix and arguments.
        
        Args:
            prefix: Key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, Model):
                key_parts.append(f"{arg.__class__.__name__}:{arg.pk}")
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments (sorted for consistency)
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, Model):
                key_parts.append(f"{key}:{value.__class__.__name__}:{value.pk}")
            else:
                key_parts.append(f"{key}:{value}")
        
        return ':'.join(key_parts)
    
    @staticmethod
    def advertiser_stats(advertiser_id: Union[str, int]) -> str:
        """Build cache key for advertiser statistics."""
        return CacheConstants.CACHE_KEYS['advertiser_stats'].format(advertiser_id=advertiser_id)
    
    @staticmethod
    def campaign_performance(campaign_id: Union[str, int]) -> str:
        """Build cache key for campaign performance."""
        return CacheConstants.CACHE_KEYS['campaign_performance'].format(campaign_id=campaign_id)
    
    @staticmethod
    def creative_performance(creative_id: Union[str, int]) -> str:
        """Build cache key for creative performance."""
        return CacheConstants.CACHE_KEYS['creative_performance'].format(creative_id=creative_id)
    
    @staticmethod
    def targeting_estimate(targeting_id: Union[str, int]) -> str:
        """Build cache key for targeting estimate."""
        return CacheConstants.CACHE_KEYS['targeting_estimate'].format(targeting_id=targeting_id)
    
    @staticmethod
    def user_permissions(user_id: Union[str, int]) -> str:
        """Build cache key for user permissions."""
        return CacheConstants.CACHE_KEYS['user_permissions'].format(user_id=user_id)
    
    @staticmethod
    def rate_limit(service: str, user_id: Union[str, int]) -> str:
        """Build cache key for rate limiting."""
        return CacheConstants.CACHE_KEYS['rate_limit'].format(service=service, user_id=user_id)
    
    @staticmethod
    def analytics_data(query_hash: str) -> str:
        """Build cache key for analytics data."""
        return f"analytics_data:{query_hash}"
    
    @staticmethod
    def billing_summary(advertiser_id: Union[str, int]) -> str:
        """Build cache key for billing summary."""
        return f"billing_summary:{advertiser_id}"


class CacheWarmer:
    """Utility class for warming up cache with common data."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def warm_advertiser_stats(self, advertiser_ids: List[Union[str, int]]) -> None:
        """Warm up cache with advertiser statistics."""
        from .services import AdvertiserService
        
        service = AdvertiserService()
        
        for advertiser_id in advertiser_ids:
            try:
                stats = service.get_advertiser_stats(advertiser_id)
                key = CacheKeyBuilder.advertiser_stats(advertiser_id)
                self.cache_manager.set(key, stats, timeout=CacheConstants.TIMEOUTS['medium'])
            except Exception as e:
                print(f"Failed to warm cache for advertiser {advertiser_id}: {e}")
    
    def warm_campaign_performance(self, campaign_ids: List[Union[str, int]]) -> None:
        """Warm up cache with campaign performance data."""
        from .services import AnalyticsService
        
        service = AnalyticsService()
        
        for campaign_id in campaign_ids:
            try:
                performance = service.get_campaign_performance(campaign_id)
                key = CacheKeyBuilder.campaign_performance(campaign_id)
                self.cache_manager.set(key, performance, timeout=CacheConstants.TIMEOUTS['short'])
            except Exception as e:
                print(f"Failed to warm cache for campaign {campaign_id}: {e}")
    
    def warm_user_permissions(self, user_ids: List[Union[str, int]]) -> None:
        """Warm up cache with user permissions."""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                permissions = list(user.get_all_permissions())
                key = CacheKeyBuilder.user_permissions(user_id)
                self.cache_manager.set(key, permissions, timeout=CacheConstants.TIMEOUTS['long'])
            except Exception as e:
                print(f"Failed to warm cache for user {user_id}: {e}")


class CacheInvalidator:
    """Utility class for invalidating cache entries."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def invalidate_advertiser_cache(self, advertiser_id: Union[str, int]) -> None:
        """Invalidate all cache entries for an advertiser."""
        patterns = [
            CacheKeyBuilder.advertiser_stats(advertiser_id),
            f"campaign_performance:*:advertiser_{advertiser_id}",
            f"creative_performance:*:advertiser_{advertiser_id}",
            CacheKeyBuilder.billing_summary(advertiser_id),
        ]
        
        for pattern in patterns:
            if '*' in pattern:
                self._invalidate_pattern(pattern)
            else:
                self.cache_manager.delete(pattern)
    
    def invalidate_campaign_cache(self, campaign_id: Union[str, int]) -> None:
        """Invalidate all cache entries for a campaign."""
        keys_to_delete = [
            CacheKeyBuilder.campaign_performance(campaign_id),
            f"creative_performance:*:campaign_{campaign_id}",
        ]
        
        for key in keys_to_delete:
            if '*' in key:
                self._invalidate_pattern(key)
            else:
                self.cache_manager.delete(key)
    
    def invalidate_creative_cache(self, creative_id: Union[str, int]) -> None:
        """Invalidate cache entries for a creative."""
        key = CacheKeyBuilder.creative_performance(creative_id)
        self.cache_manager.delete(key)
    
    def invalidate_user_cache(self, user_id: Union[str, int]) -> None:
        """Invalidate cache entries for a user."""
        key = CacheKeyBuilder.user_permissions(user_id)
        self.cache_manager.delete(key)
        
        # Also invalidate rate limit keys
        for service in ['api', 'analytics', 'billing']:
            rate_limit_key = CacheKeyBuilder.rate_limit(service, user_id)
            self.cache_manager.delete(rate_limit_key)
    
    def _invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache keys matching pattern."""
        # This requires cache backend that supports pattern matching
        # For Redis, you would use: cache.delete_pattern(pattern)
        # For now, just log the operation
        import logging
        
        logger = logging.getLogger('cache.invalidation')
        logger.info(f"Would invalidate cache pattern: {pattern}")


# Decorators for caching
def cached_result(key_template: str, timeout: Optional[int] = None, 
                 cache_manager: Optional[CacheManager] = None):
    """
    Decorator for caching function results.
    
    Args:
        key_template: Template for cache key
        timeout: Cache timeout in seconds
        cache_manager: Cache manager instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided cache manager or create default one
            cm = cache_manager or CacheManager()
            
            # Generate cache key
            cache_key = key_template.format(*args, **kwargs)
            
            # Try to get from cache
            cached_result = cm.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cm.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def cached_query(timeout: int = CacheConstants.TIMEOUTS['medium'],
                cache_manager: Optional[CacheManager] = None):
    """
    Decorator for caching database query results.
    
    Args:
        timeout: Cache timeout in seconds
        cache_manager: Cache manager instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cm = cache_manager or CacheManager()
            
            # Generate cache key based on function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key = f"query:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cm.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute query and cache result
            result = func(*args, **kwargs)
            cm.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def cache_invalidate(patterns: List[str], cache_manager: Optional[CacheManager] = None):
    """
    Decorator for invalidating cache after function execution.
    
    Args:
        patterns: List of cache key patterns to invalidate
        cache_manager: Cache manager instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cm = cache_manager or CacheManager()
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Invalidate cache patterns
            invalidator = CacheInvalidator(cm)
            for pattern in patterns:
                if '*' in pattern:
                    invalidator._invalidate_pattern(pattern)
                else:
                    # Format pattern with function arguments
                    try:
                        key = pattern.format(*args, **kwargs)
                        cm.delete(key)
                    except (KeyError, IndexError):
                        # Skip if pattern formatting fails
                        continue
            
            return result
        
        return wrapper
    return decorator


# Global cache manager instance
cache_manager = CacheManager()
cache_warmer = CacheWarmer(cache_manager)
cache_invalidator = CacheInvalidator(cache_manager)


# Utility functions
def get_cached_advertiser_stats(advertiser_id: Union[str, int]) -> Optional[Dict[str, Any]]:
    """Get advertiser statistics from cache."""
    key = CacheKeyBuilder.advertiser_stats(advertiser_id)
    return cache_manager.get(key)


def set_cached_advertiser_stats(advertiser_id: Union[str, int], 
                               stats: Dict[str, Any]) -> None:
    """Set advertiser statistics in cache."""
    key = CacheKeyBuilder.advertiser_stats(advertiser_id)
    cache_manager.set(key, stats, timeout=CacheConstants.TIMEOUTS['medium'])


def invalidate_advertiser_cache(advertiser_id: Union[str, int]) -> None:
    """Invalidate all cache entries for an advertiser."""
    cache_invalidator.invalidate_advertiser_cache(advertiser_id)


def get_cached_campaign_performance(campaign_id: Union[str, int]) -> Optional[Dict[str, Any]]:
    """Get campaign performance from cache."""
    key = CacheKeyBuilder.campaign_performance(campaign_id)
    return cache_manager.get(key)


def set_cached_campaign_performance(campaign_id: Union[str, int], 
                                  performance: Dict[str, Any]) -> None:
    """Set campaign performance in cache."""
    key = CacheKeyBuilder.campaign_performance(campaign_id)
    cache_manager.set(key, performance, timeout=CacheConstants.TIMEOUTS['short'])


def invalidate_campaign_cache(campaign_id: Union[str, int]) -> None:
    """Invalidate all cache entries for a campaign."""
    cache_invalidator.invalidate_campaign_cache(campaign_id)

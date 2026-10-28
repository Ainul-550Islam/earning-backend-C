# api/rate_limit/caching.py
"""
Caching system for rate limit module.

Provides optimized caching strategies for rate limiting operations.
"""

import logging
import json
import pickle
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class CacheStrategy:
    """Enumeration of caching strategies."""
    
    SIMPLE = 'simple'
    MULTI_LEVEL = 'multi_level'
    DISTRIBUTED = 'distributed'
    WRITE_THROUGH = 'write_through'
    WRITE_BEHIND = 'write_behind'
    CACHE_ASIDE = 'cache_aside'
    
    CHOICES = [
        (SIMPLE, 'Simple'),
        (MULTI_LEVEL, 'Multi-Level'),
        (DISTRIBUTED, 'Distributed'),
        (WRITE_THROUGH, 'Write-Through'),
        (WRITE_BEHIND, 'Write-Behind'),
        (CACHE_ASIDE, 'Cache-Aside'),
    ]


class CacheKeyManager:
    """Manages cache key generation and organization."""
    
    def __init__(self, prefix: str = 'rate_limit'):
        self.prefix = prefix
        self.version = 1
    
    def generate_key(self, *parts, version: int = None) -> str:
        """
        Generate cache key with proper formatting.
        
        Args:
            *parts: Key parts
            version: Key version
            
        Returns:
            Formatted cache key
        """
        if version is None:
            version = self.version
        
        # Join parts with proper separators
        key_parts = [self.prefix, f"v{version}"]
        key_parts.extend([str(part) for part in parts])
        
        return ":".join(key_parts)
    
    def generate_rate_limit_key(self, identifier: str, limit_type: str, 
                               time_unit: str, time_value: int) -> str:
        """Generate rate limit cache key."""
        return self.generate_key('rate_limit', identifier, limit_type, time_unit, str(time_value))
    
    def generate_user_profile_key(self, user_id: int) -> str:
        """Generate user profile cache key."""
        return self.generate_key('user_profile', str(user_id))
    
    def generate_config_key(self, config_id: int) -> str:
        """Generate configuration cache key."""
        return self.generate_key('config', str(config_id))
    
    def generate_stats_key(self, stat_type: str, *identifiers) -> str:
        """Generate statistics cache key."""
        return self.generate_key('stats', stat_type, *identifiers)
    
    def generate_analytics_key(self, analysis_type: str, *identifiers) -> str:
        """Generate analytics cache key."""
        return self.generate_key('analytics', analysis_type, *identifiers)
    
    def generate_health_key(self, component: str) -> str:
        """Generate health check cache key."""
        return self.generate_key('health', component)


class CacheEntry:
    """Represents a cache entry with metadata."""
    
    def __init__(self, key: str, value: Any, ttl: int = None, 
                 created_at: datetime = None, metadata: Dict[str, Any] = None):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.created_at = created_at or timezone.now()
        self.metadata = metadata or {}
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        
        return timezone.now() > self.created_at + timedelta(seconds=self.ttl)
    
    def access(self) -> Any:
        """Access the cache entry."""
        self.access_count += 1
        self.last_accessed = timezone.now()
        return self.value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cache entry to dictionary."""
        return {
            'key': self.key,
            'value': self.value,
            'ttl': self.ttl,
            'created_at': self.created_at.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat(),
            'metadata': self.metadata
        }


class CacheManager:
    """
    Advanced cache manager with multiple strategies.
    """
    
    def __init__(self, strategy: str = CacheStrategy.CACHE_ASIDE):
        self.strategy = strategy
        self.key_manager = CacheKeyManager()
        self.local_cache = {}
        self.local_cache_size = 1000
        self.local_cache_ttl = 300  # 5 minutes
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        try:
            # Check local cache first
            if self.strategy in [CacheStrategy.MULTI_LEVEL, CacheStrategy.CACHE_ASIDE]:
                local_entry = self._get_from_local(key)
                if local_entry and not local_entry.is_expired():
                    self.stats['hits'] += 1
                    return local_entry.access()
            
            # Check distributed cache
            value = cache.get(key, default)
            
            if value is not None and value is not default:
                self.stats['hits'] += 1
                
                # Store in local cache if using multi-level strategy
                if self.strategy == CacheStrategy.MULTI_LEVEL:
                    self._set_in_local(key, value, self.local_cache_ttl)
                
                return value
            else:
                self.stats['misses'] += 1
                return default
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {str(e)}")
            self.stats['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if set successfully
        """
        try:
            # Set in distributed cache
            success = cache.set(key, value, ttl)
            
            if success:
                self.stats['sets'] += 1
                
                # Set in local cache if using multi-level or write-through strategy
                if self.strategy in [CacheStrategy.MULTI_LEVEL, CacheStrategy.WRITE_THROUGH]:
                    self._set_in_local(key, value, ttl or self.local_cache_ttl)
            
            return success
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted successfully
        """
        try:
            # Delete from distributed cache
            success = cache.delete(key)
            
            if success:
                self.stats['deletes'] += 1
                
                # Delete from local cache
                if key in self.local_cache:
                    del self.local_cache[key]
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs
        """
        result = {}
        
        try:
            # Get from distributed cache
            cached_values = cache.get_many(keys)
            
            for key in keys:
                value = cached_values.get(key)
                if value is not None:
                    result[key] = value
                    self.stats['hits'] += 1
                else:
                    self.stats['misses'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {str(e)}")
            self.stats['misses'] += len(keys)
            return {}
    
    def set_many(self, mapping: Dict[str, Any], ttl: int = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            True if set successfully
        """
        try:
            success = cache.set_many(mapping, ttl)
            
            if success:
                self.stats['sets'] += len(mapping)
                
                # Set in local cache if using multi-level strategy
                if self.strategy == CacheStrategy.MULTI_LEVEL:
                    for key, value in mapping.items():
                        self._set_in_local(key, value, ttl or self.local_cache_ttl)
            
            return success
            
        except Exception as e:
            logger.error(f"Cache set_many error: {str(e)}")
            return False
    
    def delete_many(self, keys: List[str]) -> bool:
        """
        Delete multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            True if deleted successfully
        """
        try:
            success = cache.delete_many(keys)
            
            if success:
                self.stats['deletes'] += len(keys)
                
                # Delete from local cache
                for key in keys:
                    if key in self.local_cache:
                        del self.local_cache[key]
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete_many error: {str(e)}")
            return False
    
    def increment(self, key: str, delta: int = 1, ttl: int = None) -> int:
        """
        Increment counter in cache.
        
        Args:
            key: Cache key
            delta: Increment amount
            ttl: Time to live in seconds
            
        Returns:
            New counter value
        """
        try:
            # Use cache.incr if available
            try:
                new_value = cache.incr(key, delta, ttl)
                self.stats['sets'] += 1
                return new_value
            except AttributeError:
                # Fallback for cache backends that don't support incr
                current_value = self.get(key, 0)
                new_value = current_value + delta
                self.set(key, new_value, ttl)
                return new_value
                
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {str(e)}")
            return 0
    
    def _get_from_local(self, key: str) -> Optional[CacheEntry]:
        """Get value from local cache."""
        entry = self.local_cache.get(key)
        
        if entry and not entry.is_expired():
            return entry
        elif entry and entry.is_expired():
            # Remove expired entry
            del self.local_cache[key]
            self.stats['evictions'] += 1
        
        return None
    
    def _set_in_local(self, key: str, value: Any, ttl: int):
        """Set value in local cache."""
        # Check cache size limit
        if len(self.local_cache) >= self.local_cache_size:
            self._evict_oldest_local()
        
        entry = CacheEntry(key, value, ttl)
        self.local_cache[key] = entry
    
    def _evict_oldest_local(self):
        """Evict oldest entry from local cache."""
        if not self.local_cache:
            return
        
        oldest_key = min(self.local_cache.keys(), 
                        key=lambda k: self.local_cache[k].last_accessed)
        del self.local_cache[oldest_key]
        self.stats['evictions'] += 1
    
    def clear(self, pattern: str = None) -> bool:
        """
        Clear cache entries.
        
        Args:
            pattern: Key pattern to clear (None for all)
            
        Returns:
            True if cleared successfully
        """
        try:
            if pattern:
                # Clear matching keys
                keys = cache.keys(pattern)
                success = cache.delete_many(keys)
                
                # Clear matching local cache entries
                local_keys_to_delete = [k for k in self.local_cache.keys() if pattern in k]
                for key in local_keys_to_delete:
                    del self.local_cache[key]
                
                self.stats['deletes'] += len(keys)
            else:
                # Clear all
                cache.clear()
                self.local_cache.clear()
                self.stats['deletes'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / max(total_requests, 1)) * 100
        
        return {
            'strategy': self.strategy,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'sets': self.stats['sets'],
            'deletes': self.stats['deletes'],
            'evictions': self.stats['evictions'],
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            'local_cache_size': len(self.local_cache),
            'local_cache_limit': self.local_cache_size
        }
    
    def reset_stats(self):
        """Reset cache statistics."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }


class RateLimitCache:
    """
    Specialized cache for rate limiting operations.
    """
    
    def __init__(self, cache_manager: CacheManager = None):
        self.cache_manager = cache_manager or CacheManager()
        self.key_manager = CacheKeyManager()
    
    def get_rate_limit_count(self, identifier: str, limit_type: str, 
                           time_unit: str, time_value: int) -> int:
        """
        Get current rate limit count.
        
        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
            time_unit: Time unit
            time_value: Time value
            
        Returns:
            Current count
        """
        key = self.key_manager.generate_rate_limit_key(identifier, limit_type, time_unit, time_value)
        return self.cache_manager.get(key, 0)
    
    def set_rate_limit_count(self, identifier: str, limit_type: str, time_unit: str, 
                           time_value: int, count: int, ttl: int = None) -> bool:
        """
        Set rate limit count.
        
        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
            time_unit: Time unit
            time_value: Time value
            count: Count value
            ttl: Time to live
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_rate_limit_key(identifier, limit_type, time_unit, time_value)
        
        if ttl is None:
            from api.rate_limit.helpers import RateLimitHelper
            ttl = RateLimitHelper.calculate_time_window(time_unit, time_value)
        
        return self.cache_manager.set(key, count, ttl)
    
    def increment_rate_limit_count(self, identifier: str, limit_type: str, time_unit: str, 
                                 time_value: int, ttl: int = None) -> int:
        """
        Increment rate limit count.
        
        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
            time_unit: Time unit
            time_value: Time value
            ttl: Time to live
            
        Returns:
            New count
        """
        key = self.key_manager.generate_rate_limit_key(identifier, limit_type, time_unit, time_value)
        
        if ttl is None:
            from api.rate_limit.helpers import RateLimitHelper
            ttl = RateLimitHelper.calculate_time_window(time_unit, time_value)
        
        return self.cache_manager.increment(key, 1, ttl)
    
    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user profile from cache.
        
        Args:
            user_id: User ID
            
        Returns:
            User profile data or None
        """
        key = self.key_manager.generate_user_profile_key(user_id)
        return self.cache_manager.get(key)
    
    def set_user_profile(self, user_id: int, profile_data: Dict[str, Any], ttl: int = 300) -> bool:
        """
        Set user profile in cache.
        
        Args:
            user_id: User ID
            profile_data: Profile data
            ttl: Time to live
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_user_profile_key(user_id)
        return self.cache_manager.set(key, profile_data, ttl)
    
    def invalidate_user_profile(self, user_id: int) -> bool:
        """
        Invalidate user profile cache.
        
        Args:
            user_id: User ID
            
        Returns:
            True if invalidated successfully
        """
        key = self.key_manager.generate_user_profile_key(user_id)
        return self.cache_manager.delete(key)
    
    def get_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        Get configuration from cache.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Configuration data or None
        """
        key = self.key_manager.generate_config_key(config_id)
        return self.cache_manager.get(key)
    
    def set_config(self, config_id: int, config_data: Dict[str, Any], ttl: int = 600) -> bool:
        """
        Set configuration in cache.
        
        Args:
            config_id: Configuration ID
            config_data: Configuration data
            ttl: Time to live
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_config_key(config_id)
        return self.cache_manager.set(key, config_data, ttl)
    
    def invalidate_config(self, config_id: int) -> bool:
        """
        Invalidate configuration cache.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            True if invalidated successfully
        """
        key = self.key_manager.generate_config_key(config_id)
        return self.cache_manager.delete(key)
    
    def get_stats(self, stat_type: str, *identifiers) -> Optional[Dict[str, Any]]:
        """
        Get statistics from cache.
        
        Args:
            stat_type: Type of statistics
            *identifiers: Additional identifiers
            
        Returns:
            Statistics data or None
        """
        key = self.key_manager.generate_stats_key(stat_type, *identifiers)
        return self.cache_manager.get(key)
    
    def set_stats(self, stat_type: str, stats_data: Dict[str, Any], ttl: int = 300, *identifiers) -> bool:
        """
        Set statistics in cache.
        
        Args:
            stat_type: Type of statistics
            stats_data: Statistics data
            ttl: Time to live
            *identifiers: Additional identifiers
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_stats_key(stat_type, *identifiers)
        return self.cache_manager.set(key, stats_data, ttl)
    
    def get_analytics(self, analysis_type: str, *identifiers) -> Optional[Dict[str, Any]]:
        """
        Get analytics data from cache.
        
        Args:
            analysis_type: Type of analytics
            *identifiers: Additional identifiers
            
        Returns:
            Analytics data or None
        """
        key = self.key_manager.generate_analytics_key(analysis_type, *identifiers)
        return self.cache_manager.get(key)
    
    def set_analytics(self, analysis_type: str, analytics_data: Dict[str, Any], ttl: int = 600, *identifiers) -> bool:
        """
        Set analytics data in cache.
        
        Args:
            analysis_type: Type of analytics
            analytics_data: Analytics data
            ttl: Time to live
            *identifiers: Additional identifiers
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_analytics_key(analysis_type, *identifiers)
        return self.cache_manager.set(key, analytics_data, ttl)
    
    def get_health_status(self, component: str) -> Optional[Dict[str, Any]]:
        """
        Get health status from cache.
        
        Args:
            component: Component name
            
        Returns:
            Health status or None
        """
        key = self.key_manager.generate_health_key(component)
        return self.cache_manager.get(key)
    
    def set_health_status(self, component: str, health_data: Dict[str, Any], ttl: int = 60) -> bool:
        """
        Set health status in cache.
        
        Args:
            component: Component name
            health_data: Health data
            ttl: Time to live
            
        Returns:
            True if set successfully
        """
        key = self.key_manager.generate_health_key(component)
        return self.cache_manager.set(key, health_data, ttl)
    
    def clear_rate_limit_cache(self, identifier: str = None):
        """
        Clear rate limit cache entries.
        
        Args:
            identifier: Specific identifier to clear (None for all)
        """
        if identifier:
            pattern = f"{self.key_manager.prefix}:v{self.key_manager.version}:rate_limit:{identifier}:*"
        else:
            pattern = f"{self.key_manager.prefix}:v{self.key_manager.version}:rate_limit:*"
        
        self.cache_manager.clear(pattern)
    
    def warm_up_cache(self, user_ids: List[int] = None, config_ids: List[int] = None):
        """
        Warm up cache with frequently accessed data.
        
        Args:
            user_ids: List of user IDs to warm up
            config_ids: List of config IDs to warm up
        """
        try:
            from api.rate_limit.repositories import RepositoryFactory
            
            repositories = RepositoryFactory.get_all_repositories()
            
            # Warm up user profiles
            if user_ids:
                profile_repo = repositories['user_rate_limit_profile']
                for user_id in user_ids:
                    profile = profile_repo.get_by_user_id(user_id)
                    if profile:
                        profile_data = {
                            'api_health_score': profile.api_health_score,
                            'suspicion_score': profile.suspicion_score,
                            'is_premium': profile.is_premium,
                            'custom_daily_limit': profile.custom_daily_limit,
                            'custom_hourly_limit': profile.custom_hourly_limit,
                        }
                        self.set_user_profile(user_id, profile_data)
            
            # Warm up configurations
            if config_ids:
                config_repo = repositories['rate_limit_config']
                for config_id in config_ids:
                    config = config_repo.get_by_id(config_id)
                    if config:
                        config_data = {
                            'name': config.name,
                            'rate_limit_type': config.rate_limit_type,
                            'requests_per_unit': config.requests_per_unit,
                            'time_unit': config.time_unit,
                            'time_value': config.time_value,
                            'is_active': config.is_active,
                        }
                        self.set_config(config_id, config_data)
            
            logger.info(f"Cache warm-up completed: {len(user_ids or [])} users, {len(config_ids or [])} configs")
            
        except Exception as e:
            logger.error(f"Cache warm-up failed: {str(e)}")


# Global cache instances
cache_manager = CacheManager()
rate_limit_cache = RateLimitCache(cache_manager)


# Export classes and functions
__all__ = [
    'CacheStrategy',
    'CacheKeyManager',
    'CacheEntry',
    'CacheManager',
    'RateLimitCache',
    'cache_manager',
    'rate_limit_cache'
]

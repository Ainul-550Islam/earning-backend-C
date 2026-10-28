# engagement/caching.py
"""
Caching system for engagement gamification.
Provides intelligent caching strategies and cache management.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import hashlib
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Caching strategies."""
    SIMPLE = "simple"
    LAZY_LOADING = "lazy_loading"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"
    REFRESH_AHEAD = "refresh_ahead"


class CacheKeyType(Enum):
    """Types of cache keys."""
    USER_DATA = "user_data"
    LEADERBOARD = "leaderboard"
    QUEST_DATA = "quest_data"
    ACHIEVEMENT_DATA = "achievement_data"
    SHOP_DATA = "shop_data"
    ANALYTICS = "analytics"
    SESSION = "session"
    TEMPORARY = "temporary"


@dataclass
class CacheConfig:
    """Cache configuration."""
    key_type: CacheKeyType
    timeout: int = 300  # 5 minutes default
    strategy: CacheStrategy = CacheStrategy.SIMPLE
    version: int = 1
    compress: bool = False
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseCacheManager(ABC):
    """Base cache manager class."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all cache entries."""
        pass
    
    def _build_key(self, key: str) -> str:
        """Build cache key with version and type."""
        return f"{self.config.key_type.value}:{self.config.version}:{key}"
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for caching."""
        if self.config.compress and isinstance(value, (dict, list, str)):
            return json.dumps(value)
        return value
    
    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize value from cache."""
        if self.config.compress and isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value


class SimpleCacheManager(BaseCacheManager):
    """Simple cache manager implementation."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            cache_key = self._build_key(key)
            value = cache.get(cache_key, default)
            
            if value != default:
                value = self._deserialize_value(value)
            
            return value
            
        except Exception as exc:
            self.logger.error(f"Failed to get cache value for key {key}: {exc}")
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        try:
            cache_key = self._build_key(key)
            serialized_value = self._serialize_value(value)
            cache_timeout = timeout or self.config.timeout
            
            return cache.set(cache_key, serialized_value, cache_timeout)
            
        except Exception as exc:
            self.logger.error(f"Failed to set cache value for key {key}: {exc}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            cache_key = self._build_key(key)
            return cache.delete(cache_key)
            
        except Exception as exc:
            self.logger.error(f"Failed to delete cache value for key {key}: {exc}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache entries for this key type."""
        try:
            # This would clear all keys matching the pattern
            # In practice, you might use cache.delete_pattern or similar
            pattern = f"{self.config.key_type.value}:*"
            cache_keys = cache.keys(pattern)
            
            deleted_count = 0
            for cache_key in cache_keys:
                if cache.delete(cache_key):
                    deleted_count += 1
            
            self.logger.info(f"Cleared {deleted_count} cache entries for {self.config.key_type.value}")
            return True
            
        except Exception as exc:
            self.logger.error(f"Failed to clear cache entries: {exc}")
            return False


class LazyLoadingCacheManager(BaseCacheManager):
    """Lazy loading cache manager."""
    
    def __init__(self, config: CacheConfig, loader: Callable[[str], Any]):
        super().__init__(config)
        self.loader = loader
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache, loading if not present."""
        try:
            cache_key = self._build_key(key)
            value = cache.get(cache_key)
            
            if value is not None:
                return self._deserialize_value(value)
            
            # Load value using loader function
            loaded_value = self.loader(key)
            if loaded_value is not None:
                self.set(key, loaded_value)
                return loaded_value
            
            return default
            
        except Exception as exc:
            self.logger.error(f"Failed to get lazy cache value for key {key}: {exc}")
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        return super().set(key, value, timeout)
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return super().delete(key)
    
    def clear(self) -> bool:
        """Clear all cache entries."""
        return super().clear()


class CacheAsideManager(BaseCacheManager):
    """Cache-aside pattern cache manager."""
    
    def __init__(self, config: CacheConfig, data_source: Any):
        super().__init__(config)
        self.data_source = data_source
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache, falling back to data source."""
        try:
            cache_key = self._build_key(key)
            value = cache.get(cache_key)
            
            if value is not None:
                return self._deserialize_value(value)
            
            # Fall back to data source
            if hasattr(self.data_source, 'get'):
                data_value = self.data_source.get(key)
                if data_value is not None:
                    self.set(key, data_value)
                    return data_value
            
            return default
            
        except Exception as exc:
            self.logger.error(f"Failed to get cache-aside value for key {key}: {exc}")
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        return super().set(key, value, timeout)
    
    def delete(self, key: str) -> bool:
        """Delete value from cache and data source."""
        try:
            # Delete from cache
            cache_deleted = self.delete(key)
            
            # Delete from data source if possible
            if hasattr(self.data_source, 'delete'):
                data_deleted = self.data_source.delete(key)
                return cache_deleted and data_deleted
            
            return cache_deleted
            
        except Exception as exc:
            self.logger.error(f"Failed to delete cache-aside value for key {key}: {exc}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache entries."""
        return super().clear()


class RefreshAheadCacheManager(BaseCacheManager):
    """Refresh-ahead cache manager."""
    
    def __init__(self, config: CacheConfig, loader: Callable[[str], Any], 
                 refresh_threshold: float = 0.8):
        super().__init__(config)
        self.loader = loader
        self.refresh_threshold = refresh_threshold
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache, refreshing if near expiry."""
        try:
            cache_key = self._build_key(key)
            
            # Check if key exists and get its remaining TTL
            value = cache.get(cache_key)
            if value is not None:
                # Check if we should refresh ahead
                if self._should_refresh_ahead(cache_key):
                    # Refresh in background (async)
                    self._refresh_background(key)
                
                return self._deserialize_value(value)
            
            # Load value using loader function
            loaded_value = self.loader(key)
            if loaded_value is not None:
                self.set(key, loaded_value)
                return loaded_value
            
            return default
            
        except Exception as exc:
            self.logger.error(f"Failed to get refresh-ahead cache value for key {key}: {exc}")
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        return super().set(key, value, timeout)
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return super().delete(key)
    
    def clear(self) -> bool:
        """Clear all cache entries."""
        return super().clear()
    
    def _should_refresh_ahead(self, cache_key: str) -> bool:
        """Check if cache entry should be refreshed ahead of expiry."""
        try:
            # This would check the TTL of the cache key
            # For now, it's a simplified implementation
            return False  # Placeholder
        except Exception:
            return False
    
    def _refresh_background(self, key: str):
        """Refresh cache entry in background."""
        try:
            # Load fresh value
            fresh_value = self.loader(key)
            if fresh_value is not None:
                self.set(key, fresh_value)
                
        except Exception as exc:
            self.logger.error(f"Failed to refresh cache key {key} in background: {exc}")


class EngagementCacheManager:
    """Main cache manager for engagement system."""
    
    def __init__(self):
        self.managers = {}
        self._setup_default_managers()
    
    def _setup_default_managers(self):
        """Setup default cache managers."""
        # User data cache
        user_config = CacheConfig(
            key_type=CacheKeyType.USER_DATA,
            timeout=1800,  # 30 minutes
            strategy=CacheStrategy.CACHE_ASIDE,
            tags=['user', 'profile']
        )
        self.managers['user_data'] = CacheAsideManager(user_config, None)
        
        # Leaderboard cache
        leaderboard_config = CacheConfig(
            key_type=CacheKeyType.LEADERBOARD,
            timeout=600,  # 10 minutes
            strategy=CacheStrategy.LAZY_LOADING,
            tags=['leaderboard', 'ranking']
        )
        self.managers['leaderboard'] = LazyLoadingCacheManager(
            leaderboard_config, 
            self._load_leaderboard
        )
        
        # Quest data cache
        quest_config = CacheConfig(
            key_type=CacheKeyType.QUEST_DATA,
            timeout=900,  # 15 minutes
            strategy=CacheStrategy.SIMPLE,
            tags=['quest', 'gamification']
        )
        self.managers['quest_data'] = SimpleCacheManager(quest_config)
        
        # Achievement data cache
        achievement_config = CacheConfig(
            key_type=CacheKeyType.ACHIEVEMENT_DATA,
            timeout=1800,  # 30 minutes
            strategy=CacheStrategy.SIMPLE,
            tags=['achievement', 'gamification']
        )
        self.managers['achievement_data'] = SimpleCacheManager(achievement_config)
        
        # Shop data cache
        shop_config = CacheConfig(
            key_type=CacheKeyType.SHOP_DATA,
            timeout=1200,  # 20 minutes
            strategy=CacheStrategy.SIMPLE,
            tags=['shop', 'monetization']
        )
        self.managers['shop_data'] = SimpleCacheManager(shop_config)
        
        # Analytics cache
        analytics_config = CacheConfig(
            key_type=CacheKeyType.ANALYTICS,
            timeout=300,  # 5 minutes
            strategy=CacheStrategy.SIMPLE,
            tags=['analytics', 'metrics']
        )
        self.managers['analytics'] = SimpleCacheManager(analytics_config)
    
    def get_manager(self, key_type: CacheKeyType) -> BaseCacheManager:
        """Get cache manager by key type."""
        return self.managers.get(key_type.value)
    
    def get_user_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get user-specific data from cache."""
        manager = self.get_manager(CacheKeyType.USER_DATA)
        if manager:
            return manager.get(f"user_{user_id}:{key}", default)
        return default
    
    def set_user_data(self, user_id: int, key: str, value: Any, timeout: int = None) -> bool:
        """Set user-specific data in cache."""
        manager = self.get_manager(CacheKeyType.USER_DATA)
        if manager:
            return manager.set(f"user_{user_id}:{key}", value, timeout)
        return False
    
    def delete_user_data(self, user_id: int, key: str) -> bool:
        """Delete user-specific data from cache."""
        manager = self.get_manager(CacheKeyType.USER_DATA)
        if manager:
            return manager.delete(f"user_{user_id}:{key}")
        return False
    
    def get_leaderboard(self, key: str, default: Any = None) -> Any:
        """Get leaderboard data from cache."""
        manager = self.get_manager(CacheKeyType.LEADERBOARD)
        if manager:
            return manager.get(key, default)
        return default
    
    def set_leaderboard(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set leaderboard data in cache."""
        manager = self.get_manager(CacheKeyType.LEADERBOARD)
        if manager:
            return manager.set(key, value, timeout)
        return False
    
    def get_quest_data(self, key: str, default: Any = None) -> Any:
        """Get quest data from cache."""
        manager = self.get_manager(CacheKeyType.QUEST_DATA)
        if manager:
            return manager.get(key, default)
        return default
    
    def set_quest_data(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set quest data in cache."""
        manager = self.get_manager(CacheKeyType.QUEST_DATA)
        if manager:
            return manager.set(key, value, timeout)
        return False
    
    def get_achievement_data(self, key: str, default: Any = None) -> Any:
        """Get achievement data from cache."""
        manager = self.get_manager(CacheKeyType.ACHIEVEMENT_DATA)
        if manager:
            return manager.get(key, default)
        return default
    
    def set_achievement_data(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set achievement data in cache."""
        manager = self.get_manager(CacheKeyType.ACHIEVEMENT_DATA)
        if manager:
            return manager.set(key, value, timeout)
        return False
    
    def get_shop_data(self, key: str, default: Any = None) -> Any:
        """Get shop data from cache."""
        manager = self.get_manager(CacheKeyType.SHOP_DATA)
        if manager:
            return manager.get(key, default)
        return default
    
    def set_shop_data(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set shop data in cache."""
        manager = self.get_manager(CacheKeyType.SHOP_DATA)
        if manager:
            return manager.set(key, value, timeout)
        return False
    
    def get_analytics(self, key: str, default: Any = None) -> Any:
        """Get analytics data from cache."""
        manager = self.get_manager(CacheKeyType.ANALYTICS)
        if manager:
            return manager.get(key, default)
        return default
    
    def set_analytics(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set analytics data in cache."""
        manager = self.get_manager(CacheKeyType.ANALYTICS)
        if manager:
            return manager.set(key, value, timeout)
        return False
    
    def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache entries for a user."""
        manager = self.get_manager(CacheKeyType.USER_DATA)
        if manager:
            # Delete all keys matching user pattern
            pattern = f"user_{user_id}:*"
            cache_keys = cache.keys(pattern)
            
            deleted_count = 0
            for cache_key in cache_keys:
                if cache.delete(cache_key):
                    deleted_count += 1
            
            logger.info(f"Invalidated {deleted_count} cache entries for user {user_id}")
    
    def invalidate_cache_by_tags(self, tags: List[str]):
        """Invalidate cache entries by tags."""
        for key_type, manager in self.managers.items():
            if any(tag in manager.config.tags for tag in tags):
                manager.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {}
        
        for key_type, manager in self.managers.items():
            try:
                # Get cache stats for this manager
                # This would integrate with your cache backend's stats
                stats[key_type] = {
                    'key_type': key_type,
                    'strategy': manager.config.strategy.value,
                    'timeout': manager.config.timeout,
                    'tags': manager.config.tags,
                    'status': 'active'
                }
            except Exception as exc:
                stats[key_type] = {
                    'key_type': key_type,
                    'status': 'error',
                    'error': str(exc)
                }
        
        return stats
    
    def _load_leaderboard(self, key: str) -> Any:
        """Load leaderboard data from database."""
        try:
            from .models.leaderboard import Leaderboard
            
            # Parse key to determine what to load
            if key == "daily_top_100":
                return list(Leaderboard.objects.filter(
                    date=timezone.now().date()
                ).order_by('rank')[:100])
            elif key == "weekly_top_100":
                week_start = timezone.now().date() - timedelta(days=7)
                return list(Leaderboard.objects.filter(
                    date__gte=week_start
                ).order_by('rank')[:100])
            else:
                return None
                
        except Exception as exc:
            self.logger.error(f"Failed to load leaderboard data for key {key}: {exc}")
            return None


# Global cache manager instance
engagement_cache_manager = EngagementCacheManager()


# ── Cache Decorators ─────────────────────────────────────────────────────

def cached_result(key_type: CacheKeyType, key_func: Callable = None, timeout: int = None):
    """Decorator to cache function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Generate key from function name and arguments
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            manager = engagement_cache_manager.get_manager(key_type)
            if manager:
                cached_result = manager.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                manager.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def cache_user_data(key_func: Callable = None, timeout: int = None):
    """Decorator to cache user-specific results."""
    return cached_result(CacheKeyType.USER_DATA, key_func, timeout)


def cache_leaderboard(key_func: Callable = None, timeout: int = None):
    """Decorator to cache leaderboard results."""
    return cached_result(CacheKeyType.LEADERBOARD, key_func, timeout)


def cache_analytics(key_func: Callable = None, timeout: int = None):
    """Decorator to cache analytics results."""
    return cached_result(CacheKeyType.ANALYTICS, key_func, timeout)


def invalidate_cache_on_change(key_type: CacheKeyType, key_func: Callable):
    """Decorator to invalidate cache when data changes."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Invalidate cache
            manager = engagement_cache_manager.get_manager(key_type)
            if manager:
                cache_key = key_func(*args, **kwargs)
                manager.delete(cache_key)
            
            return result
        return wrapper
    return decorator


# ── Cache Utilities ─────────────────────────────────────────────────────

class CacheUtils:
    """Utility functions for caching."""
    
    @staticmethod
    def generate_cache_key(*parts, prefix: str = "") -> str:
        """Generate cache key from parts."""
        if prefix:
            parts = [prefix] + list(parts)
        return ":".join(str(part) for part in parts)
    
    @staticmethod
    def hash_cache_key(key: str) -> str:
        """Hash cache key for consistent length."""
        return hashlib.md5(key.encode()).hexdigest()
    
    @staticmethod
    def get_cache_size_estimate() -> int:
        """Get estimated cache size."""
        try:
            # This would integrate with your cache backend's size reporting
            # For now, it's a placeholder
            return 0
        except Exception:
            return 0
    
    @staticmethod
    def warm_cache(user_ids: List[int] = None):
        """Warm cache with frequently accessed data."""
        try:
            # Warm user data cache
            if user_ids:
                for user_id in user_ids:
                    # Pre-load user profile data
                    profile_data = engagement_cache_manager.get_user_data(
                        user_id, "profile"
                    )
                    if profile_data is None:
                        # Load from database and cache
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        
                        try:
                            user = User.objects.get(id=user_id)
                            profile_data = {
                                'id': user.id,
                                'username': user.username,
                                'email': user.email,
                                'date_joined': user.date_joined.isoformat()
                            }
                            engagement_cache_manager.set_user_data(
                                user_id, "profile", profile_data
                            )
                        except User.DoesNotExist:
                            continue
            
            # Warm leaderboard cache
            leaderboard_data = engagement_cache_manager.get_leaderboard("daily_top_100")
            if leaderboard_data is None:
                engagement_cache_manager.set_leaderboard("daily_top_100", [])
            
            logger.info("Cache warming completed")
            
        except Exception as exc:
            logger.error(f"Failed to warm cache: {exc}")
    
    @staticmethod
    def cleanup_expired_cache():
        """Clean up expired cache entries."""
        try:
            # This would integrate with your cache backend's cleanup
            # For now, it's a placeholder
            logger.info("Cache cleanup completed")
            
        except Exception as exc:
            logger.error(f"Failed to cleanup cache: {exc}")
    
    @staticmethod
    def monitor_cache_performance():
        """Monitor cache performance metrics."""
        try:
            stats = engagement_cache_manager.get_cache_stats()
            
            # Log cache performance
            for key_type, stat in stats.items():
                if stat.get('status') == 'active':
                    logger.info(f"Cache {key_type}: {stat['strategy']} strategy, {stat['timeout']}s timeout")
                else:
                    logger.warning(f"Cache {key_type}: {stat.get('error', 'Unknown error')}")
            
            return stats
            
        except Exception as exc:
            logger.error(f"Failed to monitor cache performance: {exc}")
            return {}

"""
⚡ Backup Caching Module

This module provides comprehensive caching capabilities for the backup system.
It includes intelligent cache management, performance optimization, and cache
strategies to improve backup system performance and reduce database load.

Features:
- Multi-level caching strategy
- Intelligent cache invalidation
- Performance monitoring
- Cache warming and preloading
- Distributed caching support
- Cache analytics and statistics
- Cache health monitoring
- Automatic cache optimization
"""

import logging
import time
import json
import pickle
import hashlib
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.core.cache.backends.base import BaseCache

# Import backup models
from .models import Backup, BackupSchedule, BackupStorageLocation

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Enumeration of caching strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"


class CacheLevel(Enum):
    """Enumeration of cache levels."""
    MEMORY = "memory"  # In-memory cache
    REDIS = "redis"    # Redis cache
    DATABASE = "database"  # Database query cache
    DISTRIBUTED = "distributed"  # Distributed cache


class CacheOperation(Enum):
    """Enumeration of cache operations."""
    GET = "get"
    SET = "set"
    DELETE = "delete"
    CLEAR = "clear"
    INCREMENT = "increment"
    DECREMENT = "decrement"


@dataclass
class CacheConfig:
    """Configuration for cache operations."""
    strategy: CacheStrategy = CacheStrategy.TTL
    level: CacheLevel = CacheLevel.MEMORY
    timeout: int = 300  # 5 minutes default
    key_prefix: str = "backup"
    version: int = 1
    compress: bool = False
    serialize_method: str = "json"  # json, pickle
    tags: List[str] = field(default_factory=list)
    max_size: Optional[int] = None
    hit_rate_threshold: float = 0.8  # 80% hit rate threshold


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    clears: int = 0
    evictions: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    avg_response_time: float = 0.0
    memory_usage: int = 0
    last_updated: datetime = field(default_factory=timezone.now)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=timezone.now)
    last_accessed: datetime = field(default_factory=timezone.now)
    access_count: int = 0
    size_bytes: int = 0
    ttl: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CacheKeyBuilder:
    """Builds cache keys with consistent formatting."""
    
    @staticmethod
    def build_key(prefix: str, identifier: str, *args: Any, **kwargs: Any) -> str:
        """Build a cache key from components."""
        parts = [prefix, identifier]
        
        # Add positional arguments
        if args:
            parts.extend(str(arg) for arg in args)
        
        # Add keyword arguments (sorted for consistency)
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            for key, value in sorted_kwargs:
                parts.append(f"{key}:{value}")
        
        # Join with colon and hash if too long
        key = ":".join(parts)
        if len(key) > 250:  # Redis key length limit
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{prefix}:{identifier}:{key_hash}"
        
        return key
    
    @staticmethod
    def build_backup_key(backup_id: str, operation: str = "data") -> str:
        """Build backup-specific cache key."""
        return CacheKeyBuilder.build_key("backup", f"{backup_id}:{operation}")
    
    @staticmethod
    def build_schedule_key(schedule_id: str, operation: str = "data") -> str:
        """Build schedule-specific cache key."""
        return CacheKeyBuilder.build_key("schedule", f"{schedule_id}:{operation}")
    
    @staticmethod
    def build_storage_key(storage_id: str, operation: str = "data") -> str:
        """Build storage-specific cache key."""
        return CacheKeyBuilder.build_key("storage", f"{storage_id}:{operation}")
    
    @staticmethod
    def build_stats_key(component: str, period: str = "daily") -> str:
        """Build statistics cache key."""
        return CacheKeyBuilder.build_key("stats", f"{component}:{period}")
    
    @staticmethod
    def build_query_key(model_name: str, query_hash: str) -> str:
        """Build query cache key."""
        return CacheKeyBuilder.build_key("query", f"{model_name}:{query_hash}")


class CacheSerializer:
    """Handles serialization and deserialization of cache values."""
    
    @staticmethod
    def serialize(value: Any, method: str = "json") -> bytes:
        """Serialize a value for caching."""
        try:
            if method == "json":
                return json.dumps(value, default=str).encode('utf-8')
            elif method == "pickle":
                return pickle.dumps(value)
            else:
                raise ValueError(f"Unsupported serialization method: {method}")
        except Exception as e:
            logger.error(f"Failed to serialize value with {method}: {e}")
            raise
    
    @staticmethod
    def deserialize(data: bytes, method: str = "json") -> Any:
        """Deserialize a cached value."""
        try:
            if method == "json":
                return json.loads(data.decode('utf-8'))
            elif method == "pickle":
                return pickle.loads(data)
            else:
                raise ValueError(f"Unsupported serialization method: {method}")
        except Exception as e:
            logger.error(f"Failed to deserialize value with {method}: {e}")
            raise


class CacheManager:
    """Advanced cache manager with multiple strategies and monitoring."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self.cache_backend = cache
        self.key_builder = CacheKeyBuilder()
        self.serializer = CacheSerializer()
        self.cache_entries = {}  # In-memory tracking for LRU/LFU
        self.max_memory_entries = getattr(settings, 'BACKUP_CACHE_MAX_MEMORY_ENTRIES', 1000)
        
        # Cache warming tasks
        self.warmup_tasks = []
        self.preload_keys = set()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        start_time = time.time()
        
        try:
            # Build full key with prefix
            full_key = self._build_full_key(key)
            
            # Get from cache backend
            value = self.cache_backend.get(full_key, default)
            
            if value is not None and value != default:
                # Cache hit
                self.stats.hits += 1
                self._update_access_info(key)
                
                # Deserialize if needed
                if self.config.serialize_method != "json" or not isinstance(value, (str, int, float, bool, dict, list)):
                    try:
                        if isinstance(value, bytes):
                            value = self.serializer.deserialize(value, self.config.serialize_method)
                    except Exception:
                        pass  # Return as-is if deserialization fails
            else:
                # Cache miss
                self.stats.misses += 1
            
            # Update statistics
            self.stats.total_requests += 1
            self._update_hit_rate()
            response_time = (time.time() - start_time) * 1000
            self._update_response_time(response_time)
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats.misses += 1
            self.stats.total_requests += 1
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None, 
            tags: Optional[List[str]] = None) -> bool:
        """Set value in cache."""
        try:
            # Build full key with prefix
            full_key = self._build_full_key(key)
            
            # Determine timeout
            cache_timeout = timeout or self.config.timeout
            
            # Serialize if needed
            if self.config.serialize_method == "pickle" or not isinstance(value, (str, int, float, bool, dict, list)):
                serialized_value = self.serializer.serialize(value, self.config.serialize_method)
            else:
                serialized_value = value
            
            # Set in cache backend
            result = self.cache_backend.set(full_key, serialized_value, cache_timeout)
            
            if result:
                self.stats.sets += 1
                
                # Track entry for LRU/LFU strategies
                self._track_entry(key, value, cache_timeout, tags or [])
                
                # Update memory usage estimate
                self._update_memory_usage()
            
            return result
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            full_key = self._build_full_key(key)
            result = self.cache_backend.delete(full_key)
            
            if result:
                self.stats.deletes += 1
                # Remove from tracking
                self.cache_entries.pop(key, None)
                self._update_memory_usage()
            
            return result
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries."""
        try:
            if pattern:
                # Clear entries matching pattern
                keys_to_clear = [k for k in self.cache_entries.keys() if pattern in k]
                cleared_count = 0
                
                for key in keys_to_clear:
                    if self.delete(key):
                        cleared_count += 1
                
                return cleared_count
            else:
                # Clear all cache entries with our prefix
                prefix = self._build_full_key("")
                # This is backend-specific, so we'll track locally
                cleared_count = len(self.cache_entries)
                self.cache_entries.clear()
                self.stats.clears += 1
                self._update_memory_usage()
                
                return cleared_count
                
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def increment(self, key: str, delta: int = 1) -> Optional[int]:
        """Increment cached integer value."""
        try:
            full_key = self._build_full_key(key)
            result = self.cache_backend.increment(full_key, delta)
            
            if result is not None:
                self.stats.increment += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None
    
    def decrement(self, key: str, delta: int = 1) -> Optional[int]:
        """Decrement cached integer value."""
        try:
            full_key = self._build_full_key(key)
            result = self.cache_backend.decrement(full_key, delta)
            
            if result is not None:
                self.stats.decrement += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Cache decrement error for key {key}: {e}")
            return None
    
    def get_or_set(self, key: str, default_func: Callable[[], Any], 
                   timeout: Optional[int] = None, tags: Optional[List[str]] = None) -> Any:
        """Get value from cache or set using default function."""
        value = self.get(key)
        
        if value is None:
            value = default_func()
            self.set(key, value, timeout, tags)
        
        return value
    
    def _build_full_key(self, key: str) -> str:
        """Build full cache key with prefix and version."""
        parts = [self.config.key_prefix]
        
        if self.config.version > 1:
            parts.append(f"v{self.config.version}")
        
        parts.append(key)
        return ":".join(parts)
    
    def _update_access_info(self, key: str) -> None:
        """Update access information for LRU/LFU tracking."""
        if key in self.cache_entries:
            entry = self.cache_entries[key]
            entry.last_accessed = timezone.now()
            entry.access_count += 1
    
    def _track_entry(self, key: str, value: Any, timeout: Optional[int], tags: List[str]) -> None:
        """Track cache entry for LRU/LFU strategies."""
        if self.config.strategy in [CacheStrategy.LRU, CacheStrategy.LFU]:
            # Estimate size
            try:
                if isinstance(value, str):
                    size = len(value.encode('utf-8'))
                elif isinstance(value, (int, float, bool)):
                    size = 8
                elif isinstance(value, (dict, list)):
                    size = len(json.dumps(value, default=str).encode('utf-8'))
                else:
                    size = len(str(value).encode('utf-8'))
            except Exception:
                size = 100  # Default estimate
            
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=timeout,
                tags=tags,
                size_bytes=size
            )
            
            self.cache_entries[key] = entry
            
            # Enforce max size
            if len(self.cache_entries) > self.max_memory_entries:
                self._evict_entries()
    
    def _evict_entries(self) -> None:
        """Evict entries based on strategy."""
        if not self.cache_entries:
            return
        
        entries_to_remove = len(self.cache_entries) - self.max_memory_entries
        
        if self.config.strategy == CacheStrategy.LRU:
            # Remove least recently used
            sorted_entries = sorted(
                self.cache_entries.values(),
                key=lambda x: x.last_accessed
            )
            for entry in sorted_entries[:entries_to_remove]:
                self.delete(entry.key)
                self.stats.evictions += 1
        
        elif self.config.strategy == CacheStrategy.LFU:
            # Remove least frequently used
            sorted_entries = sorted(
                self.cache_entries.values(),
                key=lambda x: x.access_count
            )
            for entry in sorted_entries[:entries_to_remove]:
                self.delete(entry.key)
                self.stats.evictions += 1
        
        else:
            # For other strategies, remove oldest entries
            sorted_entries = sorted(
                self.cache_entries.values(),
                key=lambda x: x.created_at
            )
            for entry in sorted_entries[:entries_to_remove]:
                self.delete(entry.key)
                self.stats.evictions += 1
    
    def _update_hit_rate(self) -> None:
        """Update hit rate statistics."""
        if self.stats.total_requests > 0:
            self.stats.hit_rate = self.stats.hits / self.stats.total_requests
            self.stats.miss_rate = self.stats.misses / self.stats.total_requests
    
    def _update_response_time(self, response_time: float) -> None:
        """Update average response time."""
        if self.stats.total_requests == 1:
            self.stats.avg_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.stats.avg_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.stats.avg_response_time
            )
    
    def _update_memory_usage(self) -> None:
        """Update memory usage estimate."""
        total_size = sum(entry.size_bytes for entry in self.cache_entries.values())
        self.stats.memory_usage = total_size
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self.stats.last_updated = timezone.now()
        return self.stats
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information."""
        return {
            "config": {
                "strategy": self.config.strategy.value,
                "level": self.config.level.value,
                "timeout": self.config.timeout,
                "key_prefix": self.config.key_prefix,
                "version": self.config.version,
                "compress": self.config.compress,
                "serialize_method": self.config.serialize_method,
                "max_size": self.config.max_size,
                "max_memory_entries": self.max_memory_entries
            },
            "stats": {
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "sets": self.stats.sets,
                "deletes": self.stats.deletes,
                "clears": self.stats.clears,
                "evictions": self.stats.evictions,
                "total_requests": self.stats.total_requests,
                "hit_rate": self.stats.hit_rate,
                "miss_rate": self.stats.miss_rate,
                "avg_response_time_ms": self.stats.avg_response_time,
                "memory_usage_bytes": self.stats.memory_usage,
                "memory_usage_mb": self.stats.memory_usage / (1024 * 1024),
                "last_updated": self.stats.last_updated.isoformat()
            },
            "entries": {
                "total": len(self.cache_entries),
                "by_tag": self._count_entries_by_tag(),
                "oldest_entry": self._get_oldest_entry(),
                "newest_entry": self._get_newest_entry()
            }
        }
    
    def _count_entries_by_tag(self) -> Dict[str, int]:
        """Count entries by tag."""
        tag_counts = {}
        for entry in self.cache_entries.values():
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts
    
    def _get_oldest_entry(self) -> Optional[Dict[str, Any]]:
        """Get oldest cache entry info."""
        if not self.cache_entries:
            return None
        
        oldest = min(self.cache_entries.values(), key=lambda x: x.created_at)
        return {
            "key": oldest.key,
            "created_at": oldest.created_at.isoformat(),
            "access_count": oldest.access_count,
            "size_bytes": oldest.size_bytes
        }
    
    def _get_newest_entry(self) -> Optional[Dict[str, Any]]:
        """Get newest cache entry info."""
        if not self.cache_entries:
            return None
        
        newest = max(self.cache_entries.values(), key=lambda x: x.created_at)
        return {
            "key": newest.key,
            "created_at": newest.created_at.isoformat(),
            "access_count": newest.access_count,
            "size_bytes": newest.size_bytes
        }
    
    def warm_up_cache(self, keys: List[str], data_loader: Callable[[str], Any]) -> int:
        """Warm up cache with predefined keys."""
        warmed_count = 0
        
        for key in keys:
            if self.get(key) is None:
                try:
                    value = data_loader(key)
                    self.set(key, value)
                    warmed_count += 1
                except Exception as e:
                    logger.error(f"Failed to warm up cache for key {key}: {e}")
        
        return warmed_count
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate cache entries by tag."""
        keys_to_invalidate = []
        
        for key, entry in self.cache_entries.items():
            if tag in entry.tags:
                keys_to_invalidate.append(key)
        
        invalidated_count = 0
        for key in keys_to_invalidate:
            if self.delete(key):
                invalidated_count += 1
        
        return invalidated_count


class BackupCacheManager:
    """Specialized cache manager for backup operations."""
    
    def __init__(self):
        self.cache_manager = CacheManager(CacheConfig(
            key_prefix="backup",
            timeout=600,  # 10 minutes
            strategy=CacheStrategy.LRU
        ))
        self.key_builder = CacheKeyBuilder()
    
    def cache_backup(self, backup_id: str, backup_data: Dict[str, Any], 
                     timeout: Optional[int] = None) -> bool:
        """Cache backup data."""
        key = self.key_builder.build_backup_key(backup_id)
        return self.cache_manager.set(key, backup_data, timeout, tags=["backup"])
    
    def get_cached_backup(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get cached backup data."""
        key = self.key_builder.build_backup_key(backup_id)
        return self.cache_manager.get(key)
    
    def invalidate_backup_cache(self, backup_id: str) -> bool:
        """Invalidate backup cache."""
        key = self.key_builder.build_backup_key(backup_id)
        return self.cache_manager.delete(key)
    
    def cache_schedule(self, schedule_id: str, schedule_data: Dict[str, Any],
                      timeout: Optional[int] = None) -> bool:
        """Cache schedule data."""
        key = self.key_builder.build_schedule_key(schedule_id)
        return self.cache_manager.set(key, schedule_data, timeout, tags=["schedule"])
    
    def get_cached_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get cached schedule data."""
        key = self.key_builder.build_schedule_key(schedule_id)
        return self.cache_manager.get(key)
    
    def cache_storage_info(self, storage_id: str, storage_data: Dict[str, Any],
                          timeout: Optional[int] = None) -> bool:
        """Cache storage information."""
        key = self.key_builder.build_storage_key(storage_id)
        return self.cache_manager.set(key, storage_data, timeout, tags=["storage"])
    
    def get_cached_storage_info(self, storage_id: str) -> Optional[Dict[str, Any]]:
        """Get cached storage information."""
        key = self.key_builder.build_storage_key(storage_id)
        return self.cache_manager.get(key)
    
    def cache_statistics(self, component: str, stats_data: Dict[str, Any],
                        period: str = "daily", timeout: Optional[int] = None) -> bool:
        """Cache statistics data."""
        key = self.key_builder.build_stats_key(component, period)
        return self.cache_manager.set(key, stats_data, timeout, tags=["stats", component])
    
    def get_cached_statistics(self, component: str, period: str = "daily") -> Optional[Dict[str, Any]]:
        """Get cached statistics data."""
        key = self.key_builder.build_stats_key(component, period)
        return self.cache_manager.get(key)
    
    def cache_query_result(self, model_name: str, query_params: Dict[str, Any],
                         result: List[Any], timeout: Optional[int] = None) -> bool:
        """Cache query result."""
        query_hash = hashlib.md5(json.dumps(query_params, sort_keys=True).encode()).hexdigest()
        key = self.key_builder.build_query_key(model_name, query_hash)
        return self.cache_manager.set(key, result, timeout, tags=["query", model_name])
    
    def get_cached_query_result(self, model_name: str, query_params: Dict[str, Any]) -> Optional[List[Any]]:
        """Get cached query result."""
        query_hash = hashlib.md5(json.dumps(query_params, sort_keys=True).encode()).hexdigest()
        key = self.key_builder.build_query_key(model_name, query_hash)
        return self.cache_manager.get(key)
    
    def invalidate_all_backup_cache(self) -> int:
        """Invalidate all backup-related cache."""
        return self.cache_manager.invalidate_by_tag("backup")
    
    def invalidate_all_schedule_cache(self) -> int:
        """Invalidate all schedule-related cache."""
        return self.cache_manager.invalidate_by_tag("schedule")
    
    def invalidate_all_storage_cache(self) -> int:
        """Invalidate all storage-related cache."""
        return self.cache_manager.invalidate_by_tag("storage")
    
    def invalidate_all_stats_cache(self) -> int:
        """Invalidate all statistics cache."""
        return self.cache_manager.invalidate_by_tag("stats")
    
    def invalidate_all_query_cache(self) -> int:
        """Invalidate all query cache."""
        return self.cache_manager.invalidate_by_tag("query")
    
    def warm_up_backup_cache(self, backup_ids: List[str]) -> int:
        """Warm up backup cache."""
        def data_loader(backup_key):
            backup_id = backup_key.split(":")[-2]  # Extract backup_id from key
            try:
                backup = Backup.objects.get(backup_id=backup_id)
                return {
                    'id': str(backup.backup_id),
                    'name': backup.name,
                    'status': backup.status,
                    'created_at': backup.created_at.isoformat(),
                    'file_size': backup.file_size,
                    'storage_type': backup.storage_type
                }
            except Backup.DoesNotExist:
                return None
        
        keys = [self.key_builder.build_backup_key(backup_id) for backup_id in backup_ids]
        return self.cache_manager.warm_up_cache(keys, data_loader)
    
    def warm_up_schedule_cache(self, schedule_ids: List[str]) -> int:
        """Warm up schedule cache."""
        def data_loader(schedule_key):
            schedule_id = schedule_key.split(":")[-2]  # Extract schedule_id from key
            try:
                schedule = BackupSchedule.objects.get(schedule_id=schedule_id)
                return {
                    'id': str(schedule.schedule_id),
                    'name': schedule.name,
                    'frequency': schedule.frequency,
                    'is_active': schedule.is_active,
                    'next_run': schedule.next_run.isoformat() if schedule.next_run else None
                }
            except BackupSchedule.DoesNotExist:
                return None
        
        keys = [self.key_builder.build_schedule_key(schedule_id) for schedule_id in schedule_ids]
        return self.cache_manager.warm_up_cache(keys, data_loader)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        return self.cache_manager.get_cache_info()


# Decorators for easy caching
def cache_result(timeout: int = 300, key_prefix: str = "", tags: Optional[List[str]] = None):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cache_manager = BackupCacheManager()
            result = cache_manager.cache_manager.get(cache_key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.cache_manager.set(cache_key, result, timeout, tags)
            
            return result
        return wrapper
    return decorator


def cache_backup_data(timeout: int = 600):
    """Decorator specifically for caching backup data."""
    return cache_result(timeout=timeout, key_prefix="backup_data", tags=["backup"])


def cache_schedule_data(timeout: int = 300):
    """Decorator specifically for caching schedule data."""
    return cache_result(timeout=timeout, key_prefix="schedule_data", tags=["schedule"])


def cache_storage_data(timeout: int = 900):
    """Decorator specifically for caching storage data."""
    return cache_result(timeout=timeout, key_prefix="storage_data", tags=["storage"])


def cache_stats_data(timeout: int = 1800):
    """Decorator specifically for caching statistics data."""
    return cache_result(timeout=timeout, key_prefix="stats_data", tags=["stats"])


# Global cache manager instance
_cache_manager: Optional[BackupCacheManager] = None


def get_backup_cache_manager() -> BackupCacheManager:
    """Get the global backup cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = BackupCacheManager()
    return _cache_manager


def cache_backup(backup_id: str, backup_data: Dict[str, Any], timeout: Optional[int] = None) -> bool:
    """Convenience function to cache backup data."""
    manager = get_backup_cache_manager()
    return manager.cache_backup(backup_id, backup_data, timeout)


def get_cached_backup(backup_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get cached backup data."""
    manager = get_backup_cache_manager()
    return manager.get_cached_backup(backup_id)


def invalidate_backup_cache(backup_id: str) -> bool:
    """Convenience function to invalidate backup cache."""
    manager = get_backup_cache_manager()
    return manager.invalidate_backup_cache(backup_id)


def get_cache_statistics() -> Dict[str, Any]:
    """Convenience function to get cache statistics."""
    manager = get_backup_cache_manager()
    return manager.get_cache_stats()

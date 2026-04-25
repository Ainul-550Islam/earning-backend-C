"""
Routing Cache Service

Caches routing decisions per user+context hash to improve
performance and reduce database load.
"""

import logging
import hashlib
import json
import time
from typing import Dict, List, Any, Optional, Union
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from ...models import RoutingDecisionLog, UserOfferHistory
from ...constants import (
    ROUTING_CACHE_TIMEOUT, USER_CACHE_TIMEOUT,
    CONTEXT_CACHE_TIMEOUT, CACHE_KEY_PREFIX,
    MAX_CACHE_SIZE, CACHE_CLEANUP_INTERVAL
)
from ...exceptions import CacheError, ConfigurationError
from ...utils import generate_cache_key, hash_context

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingCacheService:
    """
    Service for managing routing-related cache operations.
    
    Provides multi-layer caching:
    - L1: In-memory cache for ultra-fast access
    - L2: Redis/Django cache for distributed access
    - L3: Database cache for persistence
    
    Performance targets:
    - Cache hit rate: >90%
    - Cache lookup: <1ms
    - Cache write: <2ms
    """
    
    def __init__(self):
        self.l1_cache = {}  # In-memory cache
        self.l1_cache_size = 0
        self.l1_max_size = 1000
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'l1_hits': 0,
            'l2_hits': 0,
            'total_lookups': 0,
            'avg_lookup_time_ms': 0.0
        }
        self.last_cleanup = timezone.now()
        self.cache_version = 1
        
        # Initialize cache backend
        self._initialize_cache_backend()
    
    def _initialize_cache_backend(self):
        """Initialize the cache backend."""
        try:
            # Test cache backend
            test_key = f"{CACHE_KEY_PREFIX}:test"
            cache.set(test_key, "test", 60)
            test_value = cache.get(test_key)
            
            if test_value != "test":
                raise ImproperlyConfigured("Cache backend is not working properly")
            
            cache.delete(test_key)
            logger.info("Cache backend initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache backend: {e}")
            raise ConfigurationError(f"Cache initialization failed: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache (L1 -> L2 -> default).
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        start_time = time.time()
        
        try:
            self.cache_stats['total_lookups'] += 1
            
            # Check L1 cache first
            l1_value = self._get_l1(key)
            if l1_value is not None:
                self.cache_stats['hits'] += 1
                self.cache_stats['l1_hits'] += 1
                self._update_lookup_stats(start_time)
                return l1_value
            
            # Check L2 cache
            l2_value = self._get_l2(key)
            if l2_value is not None:
                self.cache_stats['hits'] += 1
                self.cache_stats['l2_hits'] += 1
                
                # Promote to L1 cache
                self._set_l1(key, l2_value)
                
                self._update_lookup_stats(start_time)
                return l2_value
            
            # Cache miss
            self.cache_stats['misses'] += 1
            self._update_lookup_stats(start_time)
            return default
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            self.cache_stats['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """
        Set value in cache (L1 and L2).
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if timeout is None:
                timeout = ROUTING_CACHE_TIMEOUT
            
            # Set L1 cache
            self._set_l1(key, value)
            
            # Set L2 cache
            success = self._set_l2(key, value, timeout)
            
            if success:
                self.cache_stats['sets'] += 1
                return True
            else:
                logger.warning(f"Failed to set cache key {key} in L2")
                return False
                
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache (L1 and L2).
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete from L1 cache
            self._delete_l1(key)
            
            # Delete from L2 cache
            success = self._delete_l2(key)
            
            if success:
                self.cache_stats['deletes'] += 1
                return True
            else:
                logger.warning(f"Failed to delete cache key {key} from L2")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache efficiently.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict of key -> value pairs
        """
        result = {}
        
        try:
            # Check L1 cache first
            l1_results = {}
            remaining_keys = []
            
            for key in keys:
                l1_value = self._get_l1(key)
                if l1_value is not None:
                    l1_results[key] = l1_value
                    self.cache_stats['l1_hits'] += 1
                else:
                    remaining_keys.append(key)
            
            # Check L2 cache for remaining keys
            if remaining_keys:
                l2_results = self._get_many_l2(remaining_keys)
                
                # Merge results and promote to L1
                for key, value in l2_results.items():
                    result[key] = value
                    self._set_l1(key, value)
                    self.cache_stats['l2_hits'] += 1
            
            # Add L1 results
            result.update(l1_results)
            
            # Update stats
            self.cache_stats['total_lookups'] += len(keys)
            self.cache_stats['hits'] += len(result)
            self.cache_stats['misses'] += len(keys) - len(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting multiple cache keys: {e}")
            return {}
    
    def set_many(self, data: Dict[str, Any], timeout: int = None) -> bool:
        """
        Set multiple values in cache efficiently.
        
        Args:
            data: Dict of key -> value pairs
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if timeout is None:
                timeout = ROUTING_CACHE_TIMEOUT
            
            # Set L1 cache
            for key, value in data.items():
                self._set_l1(key, value)
            
            # Set L2 cache
            success = self._set_many_l2(data, timeout)
            
            if success:
                self.cache_stats['sets'] += len(data)
                return True
            else:
                logger.warning("Failed to set multiple cache keys in L2")
                return False
                
        except Exception as e:
            logger.error(f"Error setting multiple cache keys: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete cache keys matching a pattern.
        
        Args:
            pattern: Pattern to match (supports * wildcard)
            
        Returns:
            Number of keys deleted
        """
        try:
            deleted_count = 0
            
            # Delete from L1 cache
            l1_keys_to_delete = []
            for key in self.l1_cache.keys():
                if self._match_pattern(key, pattern):
                    l1_keys_to_delete.append(key)
            
            for key in l1_keys_to_delete:
                self._delete_l1(key)
                deleted_count += 1
            
            # Delete from L2 cache
            l2_deleted = self._delete_pattern_l2(pattern)
            deleted_count += l2_deleted
            
            self.cache_stats['deletes'] += deleted_count
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting cache pattern {pattern}: {e}")
            return 0
    
    def increment(self, key: str, delta: int = 1, timeout: int = None) -> int:
        """
        Increment a cached integer value.
        
        Args:
            key: Cache key
            delta: Amount to increment
            timeout: Cache timeout for new values
            
        Returns:
            New value after increment
        """
        try:
            # Try to get current value
            current_value = self.get(key, 0)
            
            if not isinstance(current_value, int):
                current_value = 0
            
            # Increment value
            new_value = current_value + delta
            
            # Set new value
            self.set(key, new_value, timeout)
            
            return new_value
            
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {e}")
            return 0
    
    def get_routing_decision(self, user_id: int, context_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached routing decision for user and context.
        
        Args:
            user_id: User ID
            context_hash: Hash of user context
            
        Returns:
            Cached routing decision or None
        """
        cache_key = f"{CACHE_KEY_PREFIX}:routing:{user_id}:{context_hash}"
        return self.get(cache_key)
    
    def set_routing_decision(self, user_id: int, context_hash: str, 
                            decision: Dict[str, Any], timeout: int = None) -> bool:
        """
        Cache routing decision for user and context.
        
        Args:
            user_id: User ID
            context_hash: Hash of user context
            decision: Routing decision data
            timeout: Cache timeout
            
        Returns:
            True if successful, False otherwise
        """
        if timeout is None:
            timeout = ROUTING_CACHE_TIMEOUT
        
        cache_key = f"{CACHE_KEY_PREFIX}:routing:{user_id}:{context_hash}"
        return self.set(cache_key, decision, timeout)
    
    def get_user_offers(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get cached offers for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of offers to return
            
        Returns:
            List of cached offers
        """
        cache_key = f"{CACHE_KEY_PREFIX}:user_offers:{user_id}"
        cached_data = self.get(cache_key)
        
        if cached_data:
            return cached_data[:limit]
        
        return []
    
    def set_user_offers(self, user_id: int, offers: List[Dict[str, Any]], 
                         timeout: int = None) -> bool:
        """
        Cache offers for a user.
        
        Args:
            user_id: User ID
            offers: List of offers to cache
            timeout: Cache timeout
            
        Returns:
            True if successful, False otherwise
        """
        if timeout is None:
            timeout = USER_CACHE_TIMEOUT
        
        cache_key = f"{CACHE_KEY_PREFIX}:user_offers:{user_id}"
        return self.set(cache_key, offers, timeout)
    
    def get_offer_scores(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached scores for an offer.
        
        Args:
            offer_id: Offer ID
            
        Returns:
            Cached offer scores or None
        """
        cache_key = f"{CACHE_KEY_PREFIX}:offer_scores:{offer_id}"
        return self.get(cache_key)
    
    def set_offer_scores(self, offer_id: int, scores: Dict[str, Any], 
                         timeout: int = None) -> bool:
        """
        Cache scores for an offer.
        
        Args:
            offer_id: Offer ID
            scores: Offer score data
            timeout: Cache timeout
            
        Returns:
            True if successful, False otherwise
        """
        if timeout is None:
            timeout = CONTEXT_CACHE_TIMEOUT
        
        cache_key = f"{CACHE_KEY_PREFIX}:offer_scores:{offer_id}"
        return self.set(cache_key, scores, timeout)
    
    def invalidate_user_cache(self, user_id: int) -> bool:
        """
        Invalidate all cache entries for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            patterns = [
                f"{CACHE_KEY_PREFIX}:routing:{user_id}:*",
                f"{CACHE_KEY_PREFIX}:user_offers:{user_id}",
                f"{CACHE_KEY_PREFIX}:user_context:{user_id}:*"
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = self.delete_pattern(pattern)
                total_deleted += deleted
            
            logger.info(f"Invalidated {total_deleted} cache entries for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating user cache for {user_id}: {e}")
            return False
    
    def invalidate_offer_cache(self, offer_id: int) -> bool:
        """
        Invalidate all cache entries for an offer.
        
        Args:
            offer_id: Offer ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            patterns = [
                f"{CACHE_KEY_PREFIX}:offer_scores:{offer_id}",
                f"{CACHE_KEY_PREFIX}:offer_data:{offer_id}:*"
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = self.delete_pattern(pattern)
                total_deleted += deleted
            
            logger.info(f"Invalidated {total_deleted} cache entries for offer {offer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating offer cache for {offer_id}: {e}")
            return False
    
    def _get_l1(self, key: str) -> Any:
        """Get value from L1 (in-memory) cache."""
        try:
            cache_entry = self.l1_cache.get(key)
            
            if cache_entry is None:
                return None
            
            # Check if entry has expired
            if cache_entry['expires_at'] and timezone.now() > cache_entry['expires_at']:
                del self.l1_cache[key]
                self.l1_cache_size -= 1
                return None
            
            return cache_entry['value']
            
        except Exception as e:
            logger.error(f"Error getting L1 cache key {key}: {e}")
            return None
    
    def _set_l1(self, key: str, value: Any, timeout: int = None):
        """Set value in L1 (in-memory) cache."""
        try:
            if timeout is None:
                timeout = ROUTING_CACHE_TIMEOUT
            
            # Check if we need to evict entries
            if self.l1_cache_size >= self.l1_max_size:
                self._evict_l1_entries()
            
            # Set cache entry
            expires_at = timezone.now() + timezone.timedelta(seconds=timeout)
            
            self.l1_cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': timezone.now(),
                'access_count': 0
            }
            
            self.l1_cache_size += 1
            
        except Exception as e:
            logger.error(f"Error setting L1 cache key {key}: {e}")
    
    def _delete_l1(self, key: str):
        """Delete value from L1 (in-memory) cache."""
        try:
            if key in self.l1_cache:
                del self.l1_cache[key]
                self.l1_cache_size = max(0, self.l1_cache_size - 1)
        except Exception as e:
            logger.error(f"Error deleting L1 cache key {key}: {e}")
    
    def _evict_l1_entries(self):
        """Evict least recently used entries from L1 cache."""
        try:
            # Sort by access count and creation time
            entries = list(self.l1_cache.items())
            entries.sort(key=lambda x: (x[1]['access_count'], x[1]['created_at']))
            
            # Evict 25% of entries
            evict_count = max(1, len(entries) // 4)
            
            for i in range(evict_count):
                key, _ = entries[i]
                if key in self.l1_cache:
                    del self.l1_cache[key]
                    self.l1_cache_size -= 1
            
            logger.debug(f"Evicted {evict_count} entries from L1 cache")
            
        except Exception as e:
            logger.error(f"Error evicting L1 cache entries: {e}")
    
    def _get_l2(self, key: str) -> Any:
        """Get value from L2 (Redis/Django) cache."""
        try:
            value = cache.get(key)
            
            if value is not None:
                # Update access stats for L1 promotion
                if key in self.l1_cache:
                    self.l1_cache[key]['access_count'] += 1
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting L2 cache key {key}: {e}")
            return None
    
    def _set_l2(self, key: str, value: Any, timeout: int) -> bool:
        """Set value in L2 (Redis/Django) cache."""
        try:
            return cache.set(key, value, timeout)
        except Exception as e:
            logger.error(f"Error setting L2 cache key {key}: {e}")
            return False
    
    def _delete_l2(self, key: str) -> bool:
        """Delete value from L2 (Redis/Django) cache."""
        try:
            return cache.delete(key)
        except Exception as e:
            logger.error(f"Error deleting L2 cache key {key}: {e}")
            return False
    
    def _get_many_l2(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from L2 cache."""
        try:
            return cache.get_many(keys)
        except Exception as e:
            logger.error(f"Error getting multiple L2 cache keys: {e}")
            return {}
    
    def _set_many_l2(self, data: Dict[str, Any], timeout: int) -> bool:
        """Set multiple values in L2 cache."""
        try:
            return cache.set_many(data, timeout)
        except Exception as e:
            logger.error(f"Error setting multiple L2 cache keys: {e}")
            return False
    
    def _delete_pattern_l2(self, pattern: str) -> int:
        """Delete keys matching pattern from L2 cache."""
        try:
            # This depends on cache backend implementation
            # For Redis, we can use SCAN with pattern matching
            # For Django cache, we need to iterate through keys
            
            deleted_count = 0
            
            # Try Redis-specific pattern deletion
            if hasattr(cache, 'delete_pattern'):
                deleted_count = cache.delete_pattern(pattern)
            else:
                # Fallback: iterate through keys (less efficient)
                # This would need a key registry or similar mechanism
                logger.warning("Pattern deletion not supported by cache backend")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting L2 cache pattern {pattern}: {e}")
            return 0
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern."""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    def _update_lookup_stats(self, start_time: float):
        """Update cache lookup performance statistics."""
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Update average lookup time
        current_avg = self.cache_stats['avg_lookup_time_ms']
        total_lookups = self.cache_stats['total_lookups']
        self.cache_stats['avg_lookup_time_ms'] = (
            (current_avg * (total_lookups - 1) + elapsed_ms) / total_lookups
        )
    
    def cleanup_expired_entries(self):
        """Clean up expired cache entries."""
        try:
            current_time = timezone.now()
            
            # Check if cleanup is needed
            if (current_time - self.last_cleanup).seconds < CACHE_CLEANUP_INTERVAL:
                return
            
            # Clean up L1 cache
            expired_keys = []
            for key, entry in self.l1_cache.items():
                if entry['expires_at'] and current_time > entry['expires_at']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.l1_cache[key]
                self.l1_cache_size -= 1
            
            self.last_cleanup = current_time
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired L1 cache entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up cache entries: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / max(1, total_requests)
        
        return {
            'total_requests': total_requests,
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'hit_rate': hit_rate,
            'l1_hits': self.cache_stats['l1_hits'],
            'l2_hits': self.cache_stats['l2_hits'],
            'sets': self.cache_stats['sets'],
            'deletes': self.cache_stats['deletes'],
            'l1_cache_size': self.l1_cache_size,
            'l1_max_size': self.l1_max_size,
            'avg_lookup_time_ms': self.cache_stats['avg_lookup_time_ms'],
            'last_cleanup': self.last_cleanup.isoformat(),
            'cache_version': self.cache_version
        }
    
    def clear_cache(self):
        """Clear all cache entries."""
        try:
            # Clear L1 cache
            self.l1_cache.clear()
            self.l1_cache_size = 0
            
            # Clear L2 cache (if supported)
            if hasattr(cache, 'clear'):
                cache.clear()
            
            # Reset stats
            self.cache_stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'deletes': 0,
                'l1_hits': 0,
                'l2_hits': 0,
                'total_lookups': 0,
                'avg_lookup_time_ms': 0.0
            }
            
            logger.info("All cache entries cleared")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache service."""
        try:
            # Test cache operations
            test_key = f"{CACHE_KEY_PREFIX}:health_check"
            test_value = {"test": "data", "timestamp": timezone.now().isoformat()}
            
            # Test set
            set_success = self.set(test_key, test_value, 60)
            
            # Test get
            retrieved_value = self.get(test_key)
            get_success = retrieved_value == test_value
            
            # Test delete
            delete_success = self.delete(test_key)
            
            # Test pattern deletion
            pattern_key = f"{CACHE_KEY_PREFIX}:pattern_test"
            self.set(pattern_key + "_1", "value1", 60)
            self.set(pattern_key + "_2", "value2", 60)
            pattern_deleted = self.delete_pattern(pattern_key + "_*")
            
            # Calculate overall health
            all_tests_passed = all([set_success, get_success, delete_success, pattern_deleted >= 2])
            
            return {
                'status': 'healthy' if all_tests_passed else 'unhealthy',
                'tests': {
                    'set': set_success,
                    'get': get_success,
                    'delete': delete_success,
                    'pattern_delete': pattern_deleted >= 2
                },
                'stats': self.get_cache_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }

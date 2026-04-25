"""
Custom Cache Backends for Offer Routing System
"""

import json
import logging
import pickle
from typing import Any, Optional, Dict
from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from .constants import (
    ROUTING_CACHE_TIMEOUT, SCORE_CACHE_TIMEOUT,
    ROUTING_CACHE_KEY, SCORE_CACHE_KEY, CAP_CACHE_KEY
)

logger = logging.getLogger(__name__)


class OfferRoutingCache(LocMemCache):
    """
    Custom cache backend for offer routing with intelligent invalidation
    and performance monitoring.
    """
    
    def __init__(self, params):
        super().__init__(params)
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0
        }
        self.key_patterns = params.get('KEY_PATTERNS', {})
        self.max_size = params.get('MAX_SIZE', 10000)
        self.eviction_policy = params.get('EVICTION_POLICY', 'lru')
        
        # Initialize performance monitoring
        self.performance_monitor = params.get('PERFORMANCE_MONITOR', True)
        
        logger.info(f"OfferRoutingCache initialized with max_size={self.max_size}")
    
    def get(self, key, default=None, version=None):
        """Get value from cache with performance tracking."""
        result = super().get(key, default, version)
        
        if result is not None:
            self.stats['hits'] += 1
            if self.performance_monitor:
                logger.debug(f"Cache HIT: {key}")
        else:
            self.stats['misses'] += 1
            if self.performance_monitor:
                logger.debug(f"Cache MISS: {key}")
        
        return result
    
    def set(self, key, value, timeout=None, version=None):
        """Set value in cache with intelligent eviction."""
        self.stats['sets'] += 1
        
        # Check if we need to evict based on max_size
        if len(self._cache) >= self.max_size:
            self._evict_oldest_entries()
        
        result = super().set(key, value, timeout, version)
        
        if self.performance_monitor:
            logger.debug(f"Cache SET: {key} (timeout: {timeout})")
        
        return result
    
    def delete(self, key):
        """Delete key from cache."""
        result = super().delete(key)
        
        if self.performance_monitor:
            logger.debug(f"Cache DELETE: {key}")
        
        return result
    
    def clear(self):
        """Clear all cache entries."""
        self.stats.update({
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0
        })
        
        result = super().clear()
        
        if self.performance_monitor:
            logger.info("Cache CLEARED")
        
        return result
    
    def get_many(self, keys):
        """Get multiple keys from cache efficiently."""
        results = {}
        for key in keys:
            results[key] = self.get(key)
        return results
    
    def set_many(self, data, timeout=None):
        """Set multiple keys efficiently."""
        for key, value in data.items():
            self.set(key, value, timeout)
    
    def _evict_oldest_entries(self):
        """Evict oldest entries based on policy."""
        if self.eviction_policy == 'lru':
            # Find least recently used entry
            oldest_key = None
            oldest_time = None
            
            for key, entry in self._cache.items():
                if hasattr(entry, 'access_time'):
                    access_time = entry.access_time
                else:
                    access_time = 0
                
                if oldest_time is None or access_time < oldest_time:
                    oldest_time = access_time
                    oldest_key = key
            
            if oldest_key:
                self.delete(oldest_key)
                self.stats['evictions'] += 1
                if self.performance_monitor:
                    logger.debug(f"Cache EVICTION: {oldest_key} (LRU)")
        
        elif self.eviction_policy == 'lfu':
            # Find least frequently used entry
            pass  # Would implement LFU logic
        
        elif self.eviction_policy == 'random':
            # Random eviction
            import random
            if self._cache:
                random_key = random.choice(list(self._cache.keys()))
                self.delete(random_key)
                self.stats['evictions'] += 1
                if self.performance_monitor:
                    logger.debug(f"Cache EVICTION: {random_key} (Random)")
    
    def get_stats(self):
        """Get cache performance statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'sets': self.stats['sets'],
            'evictions': self.stats['evictions'],
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'current_size': len(self._cache),
            'max_size': self.max_size,
            'eviction_policy': self.eviction_policy
        }
    
    def invalidate_by_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        keys_to_delete = []
        
        for key in list(self._cache.keys()):
            if pattern in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            self.delete(key)
        
        if self.performance_monitor:
            logger.info(f"Cache INVALIDATED pattern '{pattern}': {len(keys_to_delete)} keys")
    
    def warm_up(self, keys_and_values: Dict[str, Any]):
        """Warm up cache with initial data."""
        for key, value in keys_and_values.items():
            self.set(key, value, timeout=3600)  # 1 hour
        
        if self.performance_monitor:
            logger.info(f"Cache WARMED UP with {len(keys_and_values)} entries")


class RedisOfferRoutingCache(BaseCache):
    """
    Redis-based cache backend for distributed offer routing with
    advanced features like pub/sub and pattern-based invalidation.
    """
    
    def __init__(self, params):
        self._params = params
        self._redis = None
        self._key_prefix = params.get('KEY_PREFIX', 'offer_routing')
        self._timeout = params.get('TIMEOUT', 300)
        self._max_connections = params.get('MAX_CONNECTIONS', 10)
        self._socket_timeout = params.get('SOCKET_TIMEOUT', 5)
        self._socket_connect_timeout = params.get('SOCKET_CONNECT_TIMEOUT', 5)
        
        # Performance tracking
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
        
        # Initialize Redis connection
        self._connect_redis()
        
        logger.info(f"RedisOfferRoutingCache initialized")
    
    def _connect_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            self._redis = redis.Redis(
                host=self._params.get('HOST', 'localhost'),
                port=self._params.get('PORT', 6379),
                db=self._params.get('DB', 0),
                password=self._params.get('PASSWORD', None),
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
                max_connections=self._max_connections,
                decode_responses=True
            )
            
            # Test connection
            self._redis.ping()
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise ImproperlyConfigured(f"Cannot connect to Redis: {e}")
    
    def get(self, key, default=None, version=None):
        """Get value from Redis with performance tracking."""
        try:
            full_key = f"{self._key_prefix}:{key}"
            result = self._redis.get(full_key)
            
            if result is not None:
                self.stats['hits'] += 1
                # Deserialize if needed
                if isinstance(result, bytes):
                    try:
                        result = pickle.loads(result)
                    except (pickle.PickleError, TypeError):
                        logger.warning(f"Failed to deserialize cache value for key {key}")
                        return default
            else:
                self.stats['misses'] += 1
            
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis GET error for key {key}: {e}")
            return default
    
    def set(self, key, value, timeout=None, version=None):
        """Set value in Redis with intelligent TTL."""
        try:
            full_key = f"{self._key_prefix}:{key}"
            
            # Serialize value
            if not isinstance(value, bytes):
                value = pickle.dumps(value)
            
            # Use provided timeout or default
            ttl = timeout or self._timeout
            
            result = self._redis.setex(full_key, ttl, value)
            self.stats['sets'] += 1
            
            logger.debug(f"Redis SET: {key} (TTL: {ttl})")
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def delete(self, key):
        """Delete key from Redis."""
        try:
            full_key = f"{self._key_prefix}:{key}"
            result = self._redis.delete(full_key)
            
            logger.debug(f"Redis DELETE: {key}")
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def clear(self):
        """Clear all cache entries with prefix."""
        try:
            pattern = f"{self._key_prefix}:*"
            keys = self._redis.keys(pattern)
            
            if keys:
                result = self._redis.delete(*keys)
                logger.info(f"Redis CLEARED {len(keys)} keys")
                return result
            
            return 0
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis CLEAR error: {e}")
            return False
    
    def get_many(self, keys):
        """Get multiple keys from Redis efficiently."""
        try:
            full_keys = [f"{self._key_prefix}:{key}" for key in keys]
            values = self._redis.mget(full_keys)
            
            results = {}
            for i, key in enumerate(keys):
                value = values[i]
                if value is not None:
                    try:
                        value = pickle.loads(value)
                    except (pickle.PickleError, TypeError):
                        logger.warning(f"Failed to deserialize cache value for key {key}")
                    self.stats['hits'] += 1
                else:
                    self.stats['misses'] += 1
                results[key] = value
            
            return results
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis MGET error: {e}")
            return {}
    
    def set_many(self, data, timeout=None):
        """Set multiple keys efficiently using pipeline."""
        try:
            ttl = timeout or self._timeout
            pipe = self._redis.pipeline()
            
            for key, value in data.items():
                full_key = f"{self._key_prefix}:{key}"
                if not isinstance(value, bytes):
                    value = pickle.dumps(value)
                pipe.setex(full_key, ttl, value)
            
            results = pipe.execute()
            self.stats['sets'] += len(data)
            
            logger.debug(f"Redis MSET: {len(data)} keys")
            return all(results)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis MSET error: {e}")
            return False
    
    def invalidate_by_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        try:
            search_pattern = f"{self._key_prefix}:{pattern}"
            keys = self._redis.keys(search_pattern)
            
            if keys:
                result = self._redis.delete(*keys)
                logger.info(f"Redis INVALIDATED pattern '{pattern}': {len(keys)} keys")
                return result
            
            return 0
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis INVALIDATE error: {e}")
            return False
    
    def publish_message(self, channel: str, message: Dict[str, Any]):
        """Publish message to Redis pub/sub channel."""
        try:
            message_json = json.dumps(message)
            result = self._redis.publish(channel, message_json)
            
            logger.debug(f"Redis PUBLISH: {channel} -> {len(message_json)} bytes")
            return result
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis PUBLISH error: {e}")
            return False
    
    def subscribe_to_channel(self, channel: str, callback):
        """Subscribe to Redis pub/sub channel."""
        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe(channel)
            
            logger.info(f"Redis SUBSCRIBED to channel: {channel}")
            
            # Listen for messages
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        callback(channel, data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON message on channel {channel}")
                        
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis SUBSCRIBE error: {e}")
    
    def get_stats(self):
        """Get Redis cache performance statistics."""
        try:
            info = self._redis.info()
            
            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'sets': self.stats['sets'],
                'errors': self.stats['errors'],
                'total_requests': self.stats['hits'] + self.stats['misses'],
                'hit_rate': (self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) * 100) if (self.stats['hits'] + self.stats['misses']) > 0 else 0,
                'redis_memory_used': info.get('used_memory', 0),
                'redis_memory_peak': info.get('used_memory_peak', 0),
                'redis_connected_clients': info.get('connected_clients', 0),
                'redis_keyspace_hits': info.get('keyspace_hits', 0),
                'redis_keyspace_misses': info.get('keyspace_misses', 0),
                'max_connections': self._max_connections
            }
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis STATS error: {e}")
            return {}
    
    def warm_up(self, keys_and_values: Dict[str, Any]):
        """Warm up Redis cache with initial data."""
        try:
            pipe = self._redis.pipeline()
            
            for key, value in keys_and_values.items():
                full_key = f"{self._key_prefix}:{key}"
                if not isinstance(value, bytes):
                    value = pickle.dumps(value)
                pipe.setex(full_key, 3600, value)  # 1 hour TTL
            
            results = pipe.execute()
            self.stats['sets'] += len(keys_and_values)
            
            logger.info(f"Redis WARMED UP with {len(keys_and_values)} entries")
            return all(results)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis WARM UP error: {e}")
            return False
    
    def close(self, **kwargs):
        """Close Redis connection."""
        if self._redis:
            self._redis.close()
            logger.info("Redis connection closed")


class HybridOfferRoutingCache:
    """
    Hybrid cache backend combining local memory and Redis for optimal performance.
    """
    
    def __init__(self, params):
        self.local_cache = OfferRoutingCache(params.get('LOCAL', {}))
        self.redis_cache = RedisOfferRoutingCache(params.get('REDIS', {}))
        self.local_max_size = params.get('LOCAL_MAX_SIZE', 1000)
        self.redis_ttl = params.get('REDIS_TTL', 3600)
        self.sync_interval = params.get('SYNC_INTERVAL', 60)
        
        logger.info("HybridOfferRoutingCache initialized")
    
    def get(self, key, default=None, version=None):
        """Get value trying local cache first, then Redis."""
        # Try local cache first
        value = self.local_cache.get(key, default, version)
        
        if value is not None:
            return value
        
        # Try Redis cache
        value = self.redis_cache.get(key, default, version)
        
        if value is not None:
            # Store in local cache for future access
            self.local_cache.set(key, value, timeout=300)  # 5 minutes local TTL
        
        return value
    
    def set(self, key, value, timeout=None, version=None):
        """Set value in both local and Redis cache."""
        # Set in Redis first
        redis_result = self.redis_cache.set(key, value, self.redis_ttl, version)
        
        if redis_result:
            # Set in local cache
            local_timeout = min(timeout or 300, self.local_max_size)
            self.local_cache.set(key, value, timeout=local_timeout)
        
        return redis_result
    
    def delete(self, key):
        """Delete from both local and Redis cache."""
        self.local_cache.delete(key)
        return self.redis_cache.delete(key)
    
    def clear(self):
        """Clear both local and Redis cache."""
        self.local_cache.clear()
        return self.redis_cache.clear()
    
    def get_stats(self):
        """Get combined cache statistics."""
        local_stats = self.local_cache.get_stats()
        redis_stats = self.redis_cache.get_stats()
        
        return {
            'local_cache': local_stats,
            'redis_cache': redis_stats,
            'combined': {
                'total_hits': local_stats['hits'] + redis_stats['hits'],
                'total_misses': local_stats['misses'] + redis_stats['misses'],
                'overall_hit_rate': (
                    (local_stats['hits'] + redis_stats['hits']) /
                    (local_stats['hits'] + redis_stats['hits'] + local_stats['misses'] + redis_stats['misses'])
                ) * 100 if (
                    local_stats['hits'] + redis_stats['hits'] + local_stats['misses'] + redis_stats['misses']
                ) > 0 else 0
            }
        }


# Cache backend factory
def get_cache_backend(backend_type: str):
    """Get cache backend instance by type."""
    backends = {
        'local': OfferRoutingCache,
        'redis': RedisOfferRoutingCache,
        'hybrid': HybridOfferRoutingCache
    }
    
    backend_class = backends.get(backend_type)
    if not backend_class:
        raise ImproperlyConfigured(f"Unknown cache backend: {backend_type}")
    
    return backend_class


# Cache utility functions
def get_routing_cache():
    """Get the routing cache instance."""
    from django.conf import settings
    cache_config = getattr(settings, 'OFFER_ROUTING_CACHE', {})
    
    backend_type = cache_config.get('BACKEND', 'local')
    backend_class = get_cache_backend(backend_type)
    
    return backend_class(cache_config)


def cache_routing_decision(user_id: int, context_hash: str, decision_data: Dict[str, Any]):
    """Cache routing decision with intelligent key generation."""
    cache = get_routing_cache()
    cache_key = ROUTING_CACHE_KEY.format(user_id=user_id, context_hash=context_hash)
    
    return cache.set(cache_key, decision_data, timeout=ROUTING_CACHE_TIMEOUT)


def get_cached_routing_decision(user_id: int, context_hash: str):
    """Get cached routing decision."""
    cache = get_routing_cache()
    cache_key = ROUTING_CACHE_KEY.format(user_id=user_id, context_hash=context_hash)
    
    return cache.get(cache_key)


def invalidate_user_routing_cache(user_id: int):
    """Invalidate all routing cache entries for a user."""
    cache = get_routing_cache()
    pattern = ROUTING_CACHE_KEY.format(user_id=user_id, context_hash='*')
    
    return cache.invalidate_by_pattern(pattern)


def cache_offer_score(offer_id: int, user_id: int, score_data: Dict[str, Any]):
    """Cache offer score with expiration."""
    cache = get_routing_cache()
    cache_key = SCORE_CACHE_KEY.format(offer_id=offer_id, user_id=user_id)
    
    return cache.set(cache_key, score_data, timeout=SCORE_CACHE_TIMEOUT)


def get_cached_offer_score(offer_id: int, user_id: int):
    """Get cached offer score."""
    cache = get_routing_cache()
    cache_key = SCORE_CACHE_KEY.format(offer_id=offer_id, user_id=user_id)
    
    return cache.get(cache_key)


def cache_user_cap(offer_id: int, user_id: int, cap_data: Dict[str, Any]):
    """Cache user cap with daily reset."""
    cache = get_routing_cache()
    cache_key = CAP_CACHE_KEY.format(offer_id=offer_id, user_id=user_id)
    
    # Calculate seconds until midnight for TTL
    from datetime import datetime, timedelta
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight <= now:
        midnight += timedelta(days=1)
    
    ttl_seconds = (midnight - now).total_seconds()
    
    return cache.set(cache_key, cap_data, timeout=ttl_seconds)


def get_cached_user_cap(offer_id: int, user_id: int):
    """Get cached user cap."""
    cache = get_routing_cache()
    cache_key = CAP_CACHE_KEY.format(offer_id=offer_id, user_id=user_id)
    
    return cache.get(cache_key)

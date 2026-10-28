# =============================================================================
# fraud_detection/caching.py
# =============================================================================
"""
Caching Layer for Fraud Detection System.

Provides Redis-based caching for risk scores, user profiles,
and frequently accessed fraud detection data with intelligent
cache management and invalidation strategies.
"""

from __future__ import annotations

import logging
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic
from dataclasses import dataclass, asdict
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import redis
from redis.exceptions import RedisError, ConnectionError

from api.fraud_detection.encryption import encrypt_sensitive_data, generate_integrity_hash
from api.fraud_detection.exceptions import CacheError
from api.fraud_detection.constants import CACHE_KEYS, CACHE_TTL


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Data class for cache entries with metadata."""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class RedisCacheManager:
    """
    Redis-based cache manager for fraud detection system.
    
    Provides intelligent caching with automatic serialization,
    compression, and cache invalidation strategies.
    """
    
    def __init__(self):
        """Initialize Redis cache manager."""
        self.redis_client = self._initialize_redis_client()
        self.default_ttl = getattr(settings, 'FRAUD_CACHE_DEFAULT_TTL', 3600)  # 1 hour
        self.max_memory_policy = getattr(settings, 'REDIS_MAX_MEMORY_POLICY', 'allkeys-lru')
        self.compression_threshold = getattr(settings, 'FRAUD_CACHE_COMPRESSION_THRESHOLD', 1024)
        self.serialization_method = getattr(settings, 'FRAUD_CACHE_SERIALIZATION', 'json')
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def _initialize_redis_client(self) -> redis.Redis:
        """Initialize Redis client with configuration."""
        try:
            redis_config = getattr(settings, 'REDIS_CONFIG', {
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'password': None,
                'socket_timeout': 5,
                'socket_connect_timeout': 5,
                'retry_on_timeout': True,
                'health_check_interval': 30
            })
            
            client = redis.Redis(protocol=2, **redis_config)
            
            # Test connection
            client.ping()
            
            logger.info("Redis cache manager initialized successfully")
            return client
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise CacheError(f"Redis connection failed: {e}")
    
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
            # Check if key exists
            if not self.redis_client.exists(key):
                self.stats['misses'] += 1
                return default
            
            # Get cached data
            cached_data = self.redis_client.get(key)
            if cached_data is None:
                self.stats['misses'] += 1
                return default
            
            # Deserialize data
            value = self._deserialize(cached_data)
            
            # Update access statistics
            self._update_access_stats(key)
            self.stats['hits'] += 1
            
            return value
            
        except RedisError as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats['errors'] += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            metadata: Additional metadata
            
        Returns:
            True if set successfully
        """
        try:
            # Serialize value
            serialized_data = self._serialize(value)
            
            # Set TTL
            cache_ttl = ttl if ttl is not None else self.default_ttl
            
            # Create cache entry
            cache_entry = CacheEntry(
                key=key,
                value=value,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(seconds=cache_ttl),
                metadata=metadata
            )
            
            # Store in Redis
            success = self.redis_client.setex(key, cache_ttl, serialized_data)
            
            if success:
                self.stats['sets'] += 1
                logger.debug(f"Cache set successful for key: {key}")
            else:
                self.stats['errors'] += 1
            
            return success
            
        except RedisError as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self.stats['errors'] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted successfully
        """
        try:
            success = self.redis_client.delete(key)
            
            if success:
                self.stats['deletes'] += 1
                logger.debug(f"Cache delete successful for key: {key}")
            
            return bool(success)
            
        except RedisError as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self.stats['errors'] += 1
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
            return bool(self.redis_client.exists(key))
        except RedisError as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            self.stats['errors'] += 1
            return False
    
    def get_ttl(self, key: str) -> int:
        """
        Get time to live for key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            return self.redis_client.ttl(key)
        except RedisError as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            self.stats['errors'] += 1
            return -2
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment numeric value in cache.
        
        Args:
            key: Cache key
            amount: Increment amount
            
        Returns:
            New value or None if error
        """
        try:
            result = self.redis_client.incrby(key, amount)
            self.stats['sets'] += 1
            return result
        except RedisError as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            self.stats['errors'] += 1
            return None
    
    def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs
        """
        result = {}
        
        try:
            # Use pipeline for efficiency
            with self.redis_client.pipeline() as pipe:
                for key in keys:
                    pipe.get(key)
                
                values = pipe.execute()
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = self._deserialize(value)
                        self._update_access_stats(key)
                        self.stats['hits'] += 1
                    except Exception as e:
                        logger.error(f"Cache deserialization error for key {key}: {e}")
                        self.stats['errors'] += 1
                else:
                    self.stats['misses'] += 1
            
            return result
            
        except RedisError as e:
            logger.error(f"Cache get multiple error: {e}")
            self.stats['errors'] += 1
            return {}
    
    def set_multiple(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            True if all set successfully
        """
        try:
            cache_ttl = ttl if ttl is not None else self.default_ttl
            
            with self.redis_client.pipeline() as pipe:
                for key, value in mapping.items():
                    serialized_data = self._serialize(value)
                    pipe.setex(key, cache_ttl, serialized_data)
                
                results = pipe.execute()
            
            success = all(results)
            if success:
                self.stats['sets'] += len(mapping)
            else:
                self.stats['errors'] += len(mapping) - sum(results)
            
            return success
            
        except RedisError as e:
            logger.error(f"Cache set multiple error: {e}")
            self.stats['errors'] += 1
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear keys matching pattern.
        
        Args:
            pattern: Redis key pattern
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.stats['deletes'] += deleted
                logger.info(f"Cleared {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except RedisError as e:
            logger.error(f"Cache clear pattern error for pattern {pattern}: {e}")
            self.stats['errors'] += 1
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_info = self.redis_client.info()
            
            return {
                'operations': self.stats,
                'redis_memory': redis_info.get('used_memory_human', 'N/A'),
                'redis_connected_clients': redis_info.get('connected_clients', 0),
                'redis_keyspace_hits': redis_info.get('keyspace_hits', 0),
                'redis_keyspace_misses': redis_info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(),
                'total_operations': sum(self.stats.values())
            }
        except RedisError as e:
            logger.error(f"Cache stats error: {e}")
            return {'operations': self.stats, 'error': str(e)}
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            if self.serialization_method == 'pickle':
                return pickle.dumps(value)
            elif self.serialization_method == 'json':
                # Handle Decimal objects
                if isinstance(value, dict):
                    serialized = json.dumps(value, cls=DjangoJSONEncoder)
                else:
                    serialized = json.dumps(value, default=str, cls=DjangoJSONEncoder)
                return serialized.encode('utf-8')
            else:
                raise CacheError(f"Unknown serialization method: {self.serialization_method}")
        except Exception as e:
            logger.error(f"Cache serialization error: {e}")
            raise CacheError(f"Failed to serialize value: {e}")
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            if self.serialization_method == 'pickle':
                return pickle.loads(data)
            elif self.serialization_method == 'json':
                return json.loads(data.decode('utf-8'))
            else:
                raise CacheError(f"Unknown serialization method: {self.serialization_method}")
        except Exception as e:
            logger.error(f"Cache deserialization error: {e}")
            raise CacheError(f"Failed to deserialize value: {e}")
    
    def _update_access_stats(self, key: str):
        """Update access statistics for key."""
        try:
            # Update last access time
            access_key = f"{key}:access"
            self.redis_client.setex(access_key, self.default_ttl, timezone.now().isoformat())
        except RedisError:
            pass  # Ignore access stats errors
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.stats['hits'] + self.stats['misses']
        if total_requests == 0:
            return 0.0
        return (self.stats['hits'] / total_requests) * 100

    def is_available(self) -> bool:
        """Return True when the Redis backend responds to ping."""
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False

    def warmup_fraud_rules(self) -> Dict[str, Any]:
        """Pre-load active fraud rules into the risk-score cache."""
        stats = {'rules_cached': 0, 'errors': 0}
        try:
            from api.fraud_detection.models import FraudRule

            rules = list(
                FraudRule.objects.filter(is_active=True).values(
                    'id', 'name', 'rule_type', 'severity', 'condition', 'action_on_trigger'
                )
            )
            cache = get_risk_score_cache()
            if cache.set_cached_rules(rules):
                stats['rules_cached'] = len(rules)
        except Exception as exc:
            logger.warning("Fraud rule cache warm-up skipped: %s", exc)
            stats['errors'] += 1
        return stats


class RiskScoreCache:
    """
    Specialized cache for risk scores and user profiles.
    
    Provides intelligent caching for fraud detection risk data
    with automatic invalidation and refresh strategies.
    """
    
    def __init__(self, cache_manager: Optional[RedisCacheManager] = None):
        """Initialize risk score cache."""
        self.cache_manager = cache_manager or RedisCacheManager()
        self.risk_score_ttl = getattr(settings, 'RISK_SCORE_CACHE_TTL', 1800)  # 30 minutes
        self.user_profile_ttl = getattr(settings, 'USER_PROFILE_CACHE_TTL', 3600)  # 1 hour
        self.ip_reputation_ttl = getattr(settings, 'IP_REPUTATION_CACHE_TTL', 7200)  # 2 hours
        self.device_fingerprint_ttl = getattr(settings, 'DEVICE_FINGERPRINT_CACHE_TTL', 86400)  # 24 hours
    
    def get_user_risk_score(self, user_id: Union[int, str]) -> Optional[int]:
        """
        Get user risk score from cache.
        
        Args:
            user_id: User ID
            
        Returns:
            Risk score or None if not cached
        """
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        cached_data = self.cache_manager.get(cache_key)
        
        if cached_data:
            return cached_data.get('risk_score')
        
        return None
    
    def set_user_risk_score(self, user_id: Union[int, str], risk_score: int,
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set user risk score in cache.
        
        Args:
            user_id: User ID
            risk_score: Risk score value
            metadata: Additional metadata
            
        Returns:
            True if set successfully
        """
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        
        cache_data = {
            'user_id': user_id,
            'risk_score': risk_score,
            'updated_at': timezone.now().isoformat(),
            'metadata': metadata or {}
        }
        
        return self.cache_manager.set(cache_key, cache_data, self.risk_score_ttl)
    
    def get_user_risk_profile(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get complete user risk profile from cache.
        
        Args:
            user_id: User ID
            
        Returns:
            Risk profile data or None if not cached
        """
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        return self.cache_manager.get(cache_key)
    
    def set_user_risk_profile(self, user_id: Union[int, str], 
                            profile_data: Dict[str, Any]) -> bool:
        """
        Set complete user risk profile in cache.
        
        Args:
            user_id: User ID
            profile_data: Risk profile data
            
        Returns:
            True if set successfully
        """
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        profile_data['cached_at'] = timezone.now().isoformat()
        
        return self.cache_manager.set(cache_key, profile_data, self.user_profile_ttl)
    
    def invalidate_user_risk_profile(self, user_id: Union[int, str]) -> bool:
        """
        Invalidate user risk profile cache.
        
        Args:
            user_id: User ID
            
        Returns:
            True if invalidated successfully
        """
        cache_key = f"{CACHE_KEYS['user_risk_score']}_{user_id}"
        return self.cache_manager.delete(cache_key)
    
    def get_ip_reputation(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Get IP reputation data from cache.
        
        Args:
            ip_address: IP address
            
        Returns:
            IP reputation data or None if not cached
        """
        cache_key = f"{CACHE_KEYS['ip_reputation']}_{ip_address}"
        return self.cache_manager.get(cache_key)
    
    def set_ip_reputation(self, ip_address: str, reputation_data: Dict[str, Any]) -> bool:
        """
        Set IP reputation data in cache.
        
        Args:
            ip_address: IP address
            reputation_data: Reputation data
            
        Returns:
            True if set successfully
        """
        cache_key = f"{CACHE_KEYS['ip_reputation']}_{ip_address}"
        reputation_data['cached_at'] = timezone.now().isoformat()
        
        return self.cache_manager.set(cache_key, reputation_data, self.ip_reputation_ttl)
    
    def get_device_fingerprint(self, device_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get device fingerprint data from cache.
        
        Args:
            device_hash: Device fingerprint hash
            
        Returns:
            Device fingerprint data or None if not cached
        """
        cache_key = f"{CACHE_KEYS['device_trust']}_{device_hash}"
        return self.cache_manager.get(cache_key)
    
    def set_device_fingerprint(self, device_hash: str, 
                             fingerprint_data: Dict[str, Any]) -> bool:
        """
        Set device fingerprint data in cache.
        
        Args:
            device_hash: Device fingerprint hash
            fingerprint_data: Fingerprint data
            
        Returns:
            True if set successfully
        """
        cache_key = f"{CACHE_KEYS['device_trust']}_{device_hash}"
        fingerprint_data['cached_at'] = timezone.now().isoformat()
        
        return self.cache_manager.set(cache_key, fingerprint_data, self.device_fingerprint_ttl)
    
    def get_fraud_detection_result(self, detection_key: str) -> Optional[Dict[str, Any]]:
        """
        Get fraud detection result from cache.
        
        Args:
            detection_key: Detection cache key
            
        Returns:
            Detection result or None if not cached
        """
        cache_key = f"fraud_detection_result_{detection_key}"
        return self.cache_manager.get(cache_key)
    
    def set_fraud_detection_result(self, detection_key: str, 
                                  result_data: Dict[str, Any],
                                  ttl: Optional[int] = None) -> bool:
        """
        Set fraud detection result in cache.
        
        Args:
            detection_key: Detection cache key
            result_data: Detection result data
            ttl: Custom TTL
            
        Returns:
            True if set successfully
        """
        cache_key = f"fraud_detection_result_{detection_key}"
        result_data['cached_at'] = timezone.now().isoformat()
        
        cache_ttl = ttl or getattr(settings, 'FRAUD_DETECTION_CACHE_TTL', 600)  # 10 minutes
        
        return self.cache_manager.set(cache_key, result_data, cache_ttl)
    
    def get_cached_rules(self, rule_type: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached fraud detection rules.
        
        Args:
            rule_type: Optional rule type filter
            
        Returns:
            List of rules or None if not cached
        """
        cache_key = f"{CACHE_KEYS['rule_patterns']}"
        all_rules = self.cache_manager.get(cache_key)
        
        if all_rules and rule_type:
            # Filter by rule type
            return [rule for rule in all_rules if rule.get('rule_type') == rule_type]
        
        return all_rules
    
    def set_cached_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """
        Set cached fraud detection rules.
        
        Args:
            rules: List of fraud detection rules
            
        Returns:
            True if set successfully
        """
        cache_key = f"{CACHE_KEYS['rule_patterns']}"
        rules_ttl = getattr(settings, 'FRAUD_RULES_CACHE_TTL', 1800)  # 30 minutes
        
        cache_data = {
            'rules': rules,
            'cached_at': timezone.now().isoformat(),
            'count': len(rules)
        }
        
        return self.cache_manager.set(cache_key, cache_data, rules_ttl)
    
    def invalidate_user_cache(self, user_id: Union[int, str]) -> bool:
        """
        Invalidate all cache entries for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if invalidated successfully
        """
        patterns = [
            f"*user_{user_id}*",
            f"*{user_id}*",
            f"fraud_detection_result_*{user_id}*"
        ]
        
        total_invalidated = 0
        for pattern in patterns:
            total_invalidated += self.cache_manager.clear_pattern(pattern)
        
        return total_invalidated > 0
    
    def warm_cache(self, user_ids: List[Union[int, str]]) -> Dict[str, int]:
        """
        Warm cache for specified users.
        
        Args:
            user_ids: List of user IDs to warm cache for
            
        Returns:
            Dictionary with warm-up statistics
        """
        stats = {
            'users_processed': 0,
            'risk_profiles_cached': 0,
            'errors': 0
        }
        
        for user_id in user_ids:
            try:
                # In practice, this would load actual data from database
                # For now, just simulate cache warming
                
                # Simulate risk profile data
                profile_data = {
                    'user_id': user_id,
                    'risk_score': 25,
                    'risk_level': 'low',
                    'last_updated': timezone.now().isoformat()
                }
                
                if self.set_user_risk_profile(user_id, profile_data):
                    stats['risk_profiles_cached'] += 1
                
                stats['users_processed'] += 1
                
            except Exception as e:
                logger.error(f"Cache warm-up error for user {user_id}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Get cache health information."""
        try:
            cache_stats = self.cache_manager.get_cache_stats()
            
            # Test cache operations
            test_key = "cache_health_test"
            test_value = {"test": True, "timestamp": timezone.now().isoformat()}
            
            # Test set
            set_success = self.cache_manager.set(test_key, test_value, 60)
            
            # Test get
            get_result = self.cache_manager.get(test_key)
            get_success = get_result == test_value
            
            # Test delete
            delete_success = self.cache_manager.delete(test_key)
            
            health_status = "healthy"
            if not (set_success and get_success and delete_success):
                health_status = "degraded"
            
            return {
                'health_status': health_status,
                'test_operations': {
                    'set': set_success,
                    'get': get_success,
                    'delete': delete_success
                },
                'cache_statistics': cache_stats,
                'configuration': {
                    'risk_score_ttl': self.risk_score_ttl,
                    'user_profile_ttl': self.user_profile_ttl,
                    'ip_reputation_ttl': self.ip_reputation_ttl,
                    'device_fingerprint_ttl': self.device_fingerprint_ttl
                }
            }
            
        except Exception as e:
            logger.error(f"Cache health check error: {e}")
            return {
                'health_status': 'unhealthy',
                'error': str(e)
            }


# Global cache instances
_redis_cache_manager = None
_risk_score_cache = None


def get_redis_cache_manager() -> RedisCacheManager:
    """Get or create Redis cache manager instance."""
    global _redis_cache_manager
    if _redis_cache_manager is None:
        _redis_cache_manager = RedisCacheManager()
    return _redis_cache_manager


def get_risk_score_cache() -> RiskScoreCache:
    """Get or create risk score cache instance."""
    global _risk_score_cache
    if _risk_score_cache is None:
        _risk_score_cache = RiskScoreCache()
    return _risk_score_cache


def cache_user_risk_score(user_id: Union[int, str], risk_score: int,
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function to cache user risk score.
    
    Args:
        user_id: User ID
        risk_score: Risk score
        metadata: Additional metadata
        
    Returns:
        True if cached successfully
    """
    cache = get_risk_score_cache()
    return cache.set_user_risk_score(user_id, risk_score, metadata)


def get_cached_user_risk_score(user_id: Union[int, str]) -> Optional[int]:
    """
    Convenience function to get cached user risk score.
    
    Args:
        user_id: User ID
        
    Returns:
        Cached risk score or None
    """
    cache = get_risk_score_cache()
    return cache.get_user_risk_score(user_id)


def cache_fraud_detection_result(detection_key: str, result_data: Dict[str, Any],
                                ttl: Optional[int] = None) -> bool:
    """
    Convenience function to cache fraud detection result.
    
    Args:
        detection_key: Detection cache key
        result_data: Detection result
        ttl: Custom TTL
        
    Returns:
        True if cached successfully
    """
    cache = get_risk_score_cache()
    return cache.set_fraud_detection_result(detection_key, result_data, ttl)


def get_cached_fraud_detection_result(detection_key: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get cached fraud detection result.
    
    Args:
        detection_key: Detection cache key
        
    Returns:
        Cached detection result or None
    """
    cache = get_risk_score_cache()
    return cache.get_fraud_detection_result(detection_key)

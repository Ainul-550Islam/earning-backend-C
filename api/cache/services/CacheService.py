from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Union, Callable
import json
import pickle
import hashlib
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CacheService(ABC):
    """
    Abstract Base Class for all Cache Services
    Defines the interface for cache operations
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        pass
    
    @abstractmethod
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment integer value"""
        pass
    
    @abstractmethod
    def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement integer value"""
        pass
    
    @abstractmethod
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        pass
    
    @abstractmethod
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        pass
    
    # Advanced methods with default implementations
    
    def get_or_set(
        self, 
        key: str, 
        default_func: Callable, 
        ttl: Optional[int] = None,
        *args, 
        **kwargs
    ) -> Any:
        """
        Get value from cache, or set it using default_func if not exists
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = default_func(*args, **kwargs)
        self.set(key, value, ttl)
        return value
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache
        Returns dict with existing keys
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache
        """
        success = True
        for key, value in data.items():
            if not self.set(key, value, ttl):
                success = False
        return success
    
    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys from cache
        Returns number of deleted keys
        """
        deleted = 0
        for key in keys:
            if self.delete(key):
                deleted += 1
        return deleted
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern
        """
        keys = self.keys(pattern)
        return self.delete_many(keys)
    
    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        pass
    
    def hget(self, hash_key: str, field: str) -> Optional[Any]:
        """Get field from hash"""
        full_key = f"{hash_key}:{field}"
        return self.get(full_key)
    
    def hset(self, hash_key: str, field: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set field in hash"""
        full_key = f"{hash_key}:{field}"
        return self.set(full_key, value, ttl)
    
    def hgetall(self, hash_key: str) -> Dict[str, Any]:
        """Get all fields from hash"""
        pattern = f"{hash_key}:*"
        keys = self.keys(pattern)
        result = {}
        for key in keys:
            field = key.split(":", 1)[1] if ":" in key else key
            value = self.get(key)
            if value is not None:
                result[field] = value
        return result
    
    def hdel(self, hash_key: str, fields: List[str]) -> int:
        """Delete fields from hash"""
        keys = [f"{hash_key}:{field}" for field in fields]
        return self.delete_many(keys)
    
    def sadd(self, set_key: str, *members: Any) -> int:
        """Add members to set"""
        existing = self.get(set_key) or set()
        if not isinstance(existing, set):
            existing = set()
        
        added = 0
        for member in members:
            if member not in existing:
                existing.add(member)
                added += 1
        
        self.set(set_key, existing)
        return added
    
    def srem(self, set_key: str, *members: Any) -> int:
        """Remove members from set"""
        existing = self.get(set_key)
        if not isinstance(existing, set):
            return 0
        
        removed = 0
        for member in members:
            if member in existing:
                existing.remove(member)
                removed += 1
        
        self.set(set_key, existing)
        return removed
    
    def smembers(self, set_key: str) -> set:
        """Get all members of set"""
        value = self.get(set_key)
        return set(value) if isinstance(value, (set, list)) else set()
    
    def publish(self, channel: str, message: Any) -> bool:
        """Publish message to channel"""
        # Default implementation - override in specific services
        logger.info(f"Publishing to {channel}: {message}")
        return True
    
    def subscribe(self, channel: str, callback: Callable) -> None:
        """Subscribe to channel"""
        # Default implementation - override in specific services
        logger.info(f"Subscribed to {channel}")
    
    # Statistics and monitoring
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "service": self.__class__.__name__,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "active"
        }
    
    def health_check(self) -> bool:
        """Health check for cache service"""
        try:
            test_key = f"_health_check_{int(time.time())}"
            self.set(test_key, "test", 1)
            value = self.get(test_key)
            self.delete(test_key)
            return value == "test"
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    # Serialization helpers
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        try:
            # Try JSON first for readability
            return json.dumps(value).encode('utf-8')
        except (TypeError, OverflowError):
            # Fall back to pickle for complex objects
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(data)
    
    # Key generation helpers
    def generate_key(
        self, 
        prefix: str, 
        *args, 
        **kwargs
    ) -> str:
        """Generate cache key from arguments"""
        parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (int, float, str, bool)):
                parts.append(str(arg))
            elif arg is None:
                parts.append("None")
            else:
                # Hash complex objects
                parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
        
        # Add keyword arguments
        for key, value in sorted(kwargs.items()):
            if isinstance(value, (int, float, str, bool)):
                parts.append(f"{key}:{value}")
            elif value is None:
                parts.append(f"{key}:None")
            else:
                parts.append(f"{key}:{hashlib.md5(str(value).encode()).hexdigest()[:8]}")
        
        return ":".join(parts)
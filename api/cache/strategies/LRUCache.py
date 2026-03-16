import threading
import time
from typing import Any, Optional, Dict, List
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

class LRUCache:
    """
    Least Recently Used (LRU) Cache implementation
    Thread-safe with size limit and TTL support
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        eviction_policy: str = 'lru'
    ):
        """
        Args:
            max_size: Maximum number of items in cache
            default_ttl: Default time-to-live in seconds
            eviction_policy: Eviction policy ('lru' or 'ttl')
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        
        # Cache storage: key -> (value, timestamp, expiry)
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Background cleanup thread
        self._cleanup_thread = None
        self._cleanup_interval = 60  # seconds
        self._running = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key in self._cache:
                value, timestamp, expiry = self._cache[key]
                
                # Check if expired
                if expiry and time.time() > expiry:
                    del self._cache[key]
                    self._evictions += 1
                    self._misses += 1
                    return None
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return value
            
            self._misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self._lock:
            # Calculate expiry
            expiry = None
            if ttl is not None:
                expiry = time.time() + ttl
            elif self.default_ttl:
                expiry = time.time() + self.default_ttl
            
            # Check if key already exists
            if key in self._cache:
                # Update existing
                self._cache[key] = (value, time.time(), expiry)
                self._cache.move_to_end(key)
            else:
                # Check if we need to evict
                if len(self._cache) >= self.max_size:
                    self._evict()
                
                # Add new item
                self._cache[key] = (value, time.time(), expiry)
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        with self._lock:
            if key not in self._cache:
                return False
            
            # Check expiry
            _, _, expiry = self._cache[key]
            if expiry and time.time() > expiry:
                del self._cache[key]
                return False
            
            return True
    
    def clear(self) -> None:
        """Clear all items from cache"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    def keys(self) -> List[str]:
        """Get all keys in cache"""
        with self._lock:
            self._cleanup_expired()
            return list(self._cache.keys())
    
    def values(self) -> List[Any]:
        """Get all values in cache"""
        with self._lock:
            self._cleanup_expired()
            return [v[0] for v in self._cache.values()]
    
    def items(self) -> List[tuple]:
        """Get all items in cache"""
        with self._lock:
            self._cleanup_expired()
            return [(k, v[0]) for k, v in self._cache.items()]
    
    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)
    
    def _evict(self):
        """Evict items based on policy"""
        if not self._cache:
            return
        
        if self.eviction_policy == 'ttl':
            # Evict expired items first
            self._cleanup_expired()
            
            # If still full, evict by LRU
            if len(self._cache) >= self.max_size:
                self._evict_lru()
        else:
            # Default: LRU eviction
            self._evict_lru()
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if self._cache:
            key, _ = self._cache.popitem(last=False)
            self._evictions += 1
            logger.debug(f"LRU eviction: {key}")
    
    def _cleanup_expired(self):
        """Remove expired items from cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, (_, _, expiry) in self._cache.items():
            if expiry and current_time > expiry:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._evictions += 1
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired items")
    
    def start_cleanup_thread(self):
        """Start background cleanup thread"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._running = True
        
        def cleanup_worker():
            while self._running:
                time.sleep(self._cleanup_interval)
                with self._lock:
                    self._cleanup_expired()
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("Started LRU cache cleanup thread")
    
    def stop_cleanup_thread(self):
        """Stop background cleanup thread"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None
            logger.info("Stopped LRU cache cleanup thread")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                'type': 'LRUCache',
                'max_size': self.max_size,
                'current_size': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'evictions': self._evictions,
                'hit_rate': f"{hit_rate:.2f}%",
                'default_ttl': self.default_ttl,
                'eviction_policy': self.eviction_policy,
                'cleanup_thread_running': self._running
            }
    
    def __contains__(self, key: str) -> bool:
        """Check if key is in cache"""
        return self.exists(key)
    
    def __len__(self) -> int:
        """Get cache size"""
        return self.size()
    
    def __getitem__(self, key: str) -> Any:
        """Get item with [] syntax"""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: str, value: Any):
        """Set item with [] syntax"""
        self.set(key, value)
    
    def __delitem__(self, key: str):
        """Delete item with del syntax"""
        if not self.delete(key):
            raise KeyError(key)

class LRUCacheService:
    """
    LRU Cache service that can be used as a drop-in replacement
    for RedisService/MemcachedService
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.cache = LRUCache(max_size=max_size, default_ttl=default_ttl)
        self.cache.start_cleanup_thread()
    
    def get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return self.cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        return self.cache.delete(key)
    
    def exists(self, key: str) -> bool:
        return self.cache.exists(key)
    
    def increment(self, key: str, amount: int = 1) -> int:
        current = self.cache.get(key) or 0
        if isinstance(current, (int, float)):
            new_value = current + amount
            self.cache.set(key, new_value)
            return new_value
        return 0
    
    def decrement(self, key: str, amount: int = 1) -> int:
        return self.increment(key, -amount)
    
    def ttl(self, key: str) -> int:
        # LRU cache doesn't support TTL queries directly
        return -1
    
    def expire(self, key: str, ttl: int) -> bool:
        value = self.cache.get(key)
        if value is not None:
            return self.cache.set(key, value, ttl)
        return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        # Simple pattern matching for LRU cache
        all_keys = self.cache.keys()
        if pattern == "*":
            return all_keys
        
        # Convert pattern to regex
        import re
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        compiled = re.compile(f'^{regex_pattern}$')
        
        return [key for key in all_keys if compiled.match(key)]
    
    def get_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()
    
    def health_check(self) -> bool:
        return True
    
    def close(self):
        self.cache.stop_cleanup_thread()
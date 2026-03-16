import threading
import time
import heapq
from typing import Any, Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TTLCache:
    """
    Time-To-Live (TTL) Cache implementation
    Efficient expiry handling using heap
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        cleanup_interval: int = 60
    ):
        """
        Args:
            max_size: Maximum number of items in cache
            default_ttl: Default time-to-live in seconds
            cleanup_interval: Background cleanup interval in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Storage: key -> (value, expiry_time)
        self._cache = {}
        
        # Expiry heap: (expiry_time, key)
        self._expiry_heap = []
        
        # Access time tracking for LRU fallback
        self._access_times = {}
        
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Background cleanup
        self._cleanup_interval = cleanup_interval
        self._cleanup_thread = None
        self._running = False
        
        # Start cleanup thread
        self.start_cleanup_thread()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                
                # Check expiry
                current_time = time.time()
                if expiry and current_time > expiry:
                    self._remove_key(key)
                    self._misses += 1
                    return None
                
                # Update access time
                self._access_times[key] = current_time
                self._hits += 1
                return value
            
            self._misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        with self._lock:
            # Calculate expiry
            if ttl is not None:
                expiry = time.time() + ttl
            else:
                expiry = time.time() + self.default_ttl
            
            # Check if key exists
            if key in self._cache:
                # Remove old expiry from heap
                self._remove_from_heap(key)
            
            # Check size limit
            if len(self._cache) >= self.max_size:
                self._evict()
            
            # Store value
            self._cache[key] = (value, expiry)
            self._access_times[key] = time.time()
            
            # Add to expiry heap
            heapq.heappush(self._expiry_heap, (expiry, key))
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            return self._remove_key(key)
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        with self._lock:
            if key not in self._cache:
                return False
            
            _, expiry = self._cache[key]
            if expiry and time.time() > expiry:
                self._remove_key(key)
                return False
            
            return True
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        with self._lock:
            if key not in self._cache:
                return -1
            
            _, expiry = self._cache[key]
            current_time = time.time()
            
            if expiry <= current_time:
                self._remove_key(key)
                return -1
            
            return int(expiry - current_time)
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        with self._lock:
            if key not in self._cache:
                return False
            
            value, old_expiry = self._cache[key]
            
            # Remove old expiry
            self._remove_from_heap(key)
            
            # Set new expiry
            new_expiry = time.time() + ttl
            self._cache[key] = (value, new_expiry)
            
            # Add to heap with new expiry
            heapq.heappush(self._expiry_heap, (new_expiry, key))
            
            return True
    
    def _remove_key(self, key: str) -> bool:
        """Remove key from all data structures"""
        if key in self._cache:
            # Remove from cache
            del self._cache[key]
            
            # Remove from access times
            if key in self._access_times:
                del self._access_times[key]
            
            # Note: Expiry heap will be cleaned up by cleanup thread
            self._evictions += 1
            return True
        
        return False
    
    def _remove_from_heap(self, key: str):
        """Remove key from expiry heap (lazy removal)"""
        # We don't remove from heap immediately, cleanup handles it
        pass
    
    def _evict(self):
        """Evict items when cache is full"""
        # First, remove expired items
        self._cleanup_expired()
        
        # If still full, use LRU
        if len(self._cache) >= self.max_size:
            self._evict_lru()
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if not self._access_times:
            # If no access times, remove random item
            key = next(iter(self._cache.keys()))
        else:
            # Find least recently accessed
            key = min(self._access_times.items(), key=lambda x: x[1])[0]
        
        self._remove_key(key)
        logger.debug(f"LRU eviction: {key}")
    
    def _cleanup_expired(self):
        """Remove expired items"""
        current_time = time.time()
        
        while self._expiry_heap and self._expiry_heap[0][0] <= current_time:
            expiry, key = heapq.heappop(self._expiry_heap)
            
            # Check if still exists and expired
            if key in self._cache:
                _, cached_expiry = self._cache[key]
                if cached_expiry == expiry:  # Ensure it's the same entry
                    self._remove_key(key)
                    logger.debug(f"Expired: {key}")
    
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
        logger.info("Started TTL cache cleanup thread")
    
    def stop_cleanup_thread(self):
        """Stop background cleanup thread"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None
            logger.info("Stopped TTL cache cleanup thread")
    
    def clear(self):
        """Clear all items from cache"""
        with self._lock:
            self._cache.clear()
            self._expiry_heap.clear()
            self._access_times.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    def keys(self) -> List[str]:
        """Get all non-expired keys"""
        with self._lock:
            self._cleanup_expired()
            return list(self._cache.keys())
    
    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            # Count expired items in heap
            current_time = time.time()
            expired_in_heap = sum(1 for expiry, _ in self._expiry_heap if expiry <= current_time)
            
            return {
                'type': 'TTLCache',
                'max_size': self.max_size,
                'current_size': len(self._cache),
                'expiry_heap_size': len(self._expiry_heap),
                'expired_in_heap': expired_in_heap,
                'hits': self._hits,
                'misses': self._misses,
                'evictions': self._evictions,
                'hit_rate': f"{hit_rate:.2f}%",
                'default_ttl': self.default_ttl,
                'cleanup_interval': self._cleanup_interval,
                'cleanup_thread_running': self._running
            }
    
    def __contains__(self, key: str) -> bool:
        return self.exists(key)
    
    def __len__(self) -> int:
        return self.size()
    
    def __del__(self):
        self.stop_cleanup_thread()

class TTLCacheService:
    """
    TTL Cache service implementation
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.cache = TTLCache(max_size=max_size, default_ttl=default_ttl)
    
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
        return self.cache.ttl(key)
    
    def expire(self, key: str, ttl: int) -> bool:
        return self.cache.expire(key, ttl)
    
    def keys(self, pattern: str = "*") -> List[str]:
        # Simple pattern matching
        all_keys = self.cache.keys()
        if pattern == "*":
            return all_keys
        
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
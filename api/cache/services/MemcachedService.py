import memcache
import pickle
import json
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime
import time
import logging
from .CacheService import CacheService

logger = logging.getLogger(__name__)

class MemcachedService(CacheService):
    """
    Memcached implementation of CacheService
    Supports multiple memcached servers
    """
    
    def __init__(
        self,
        servers: List[str] = ['localhost:11211'],
        debug: bool = False,
        socket_timeout: float = 3.0,
        connect_timeout: float = 3.0,
        server_max_key_length: int = 250,
        server_max_value_length: int = 1048576,  # 1MB
        pickler: Callable = pickle.dumps,
        unpickler: Callable = pickle.loads
    ):
        """
        Initialize Memcached service
        
        Args:
            servers: List of memcached servers
            debug: Enable debug mode
            socket_timeout: Socket timeout in seconds
            connect_timeout: Connection timeout in seconds
            server_max_key_length: Maximum key length
            server_max_value_length: Maximum value length
            pickler: Function to serialize data
            unpickler: Function to deserialize data
        """
        self.servers = servers
        self.debug = debug
        self.server_max_key_length = server_max_key_length
        self.server_max_value_length = server_max_value_length
        self.pickler = pickler
        self.unpickler = unpickler
        
        # Initialize memcached client
        self._client = memcache.Client(
            servers=servers,
            debug=debug,
            socket_timeout=socket_timeout,
            connect_timeout=connect_timeout,
            pickler=pickler,
            unpickler=unpickler
        )
        
        # Test connection
        self.health_check()
        
        logger.info(f"Connected to Memcached servers: {servers}")
    
    @property
    def client(self):
        """Get memcached client"""
        return self._client
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from memcached"""
        try:
            # Memcached has key length limit
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                logger.warning(f"Key too long, using hash: {key} -> {key_hash}")
                key = key_hash
            
            value = self.client.get(key)
            
            # Handle compression if used
            if isinstance(value, bytes) and value.startswith(b'COMPRESSED:'):
                import zlib
                compressed = value[11:]
                value = self.unpickler(zlib.decompress(compressed))
            
            return value
        
        except Exception as e:
            logger.error(f"Error getting key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in memcached"""
        try:
            # Memcached has key length limit
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                logger.warning(f"Key too long, using hash: {key} -> {key_hash}")
                key = key_hash
            
            # Check value size
            serialized = self.pickler(value)
            if len(serialized) > self.server_max_value_length:
                # Try compression
                import zlib
                compressed = zlib.compress(serialized)
                if len(compressed) + 11 <= self.server_max_value_length:  # +11 for 'COMPRESSED:' prefix
                    value = b'COMPRESSED:' + compressed
                else:
                    logger.error(f"Value too large for key {key}: {len(serialized)} bytes")
                    return False
            
            # Convert ttl: None = forever, 0 = default, >0 = seconds
            if ttl is None:
                ttl = 0  # Memcached: 0 means never expire
            elif ttl <= 0:
                ttl = 0
            
            # Memcached max ttl is 30 days in seconds
            if ttl > 2592000:
                ttl = 2592000
            
            return self.client.set(key, value, time=ttl)
        
        except Exception as e:
            logger.error(f"Error setting key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from memcached"""
        try:
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                key = key_hash
            
            # time=0 means delete immediately
            return self.client.delete(key, time=0)
        
        except Exception as e:
            logger.error(f"Error deleting key {key}: {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in memcached"""
        try:
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                key = key_hash
            
            value = self.client.get(key)
            return value is not None
        
        except Exception as e:
            logger.error(f"Error checking key {key}: {str(e)}")
            return False
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment integer value in memcached"""
        try:
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                key = key_hash
            
            # Memcached increment returns new value or None
            result = self.client.incr(key, amount)
            return result if result is not None else 0
        
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0
    
    def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement integer value in memcached"""
        try:
            if len(key) > self.server_max_key_length:
                key_hash = self._hash_key(key)
                key = key_hash
            
            result = self.client.decr(key, amount)
            return result if result is not None else 0
        
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {str(e)}")
            return 0
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        # Memcached doesn't support getting TTL directly
        # We'll store TTL in a separate key
        ttl_key = f"{key}:ttl"
        ttl_value = self.get(ttl_key)
        
        if ttl_value and isinstance(ttl_value, (int, float)):
            remaining = ttl_value - time.time()
            return max(0, int(remaining))
        
        return -1
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        try:
            # Get current value
            value = self.get(key)
            if value is None:
                return False
            
            # Re-set with new TTL
            return self.set(key, value, ttl)
        
        except Exception as e:
            logger.error(f"Error setting expire for key {key}: {str(e)}")
            return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching pattern
        Note: Memcached doesn't support key listing natively
        This is an approximation using stats
        """
        # Memcached doesn't support listing keys directly
        # We can use stats cachedump but it's not reliable
        logger.warning("Memcached doesn't support key listing efficiently")
        return []
    
    # Advanced operations with workarounds
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from memcached"""
        try:
            # Handle long keys
            key_map = {}
            memcache_keys = []
            
            for key in keys:
                if len(key) > self.server_max_key_length:
                    key_hash = self._hash_key(key)
                    key_map[key_hash] = key
                    memcache_keys.append(key_hash)
                else:
                    key_map[key] = key
                    memcache_keys.append(key)
            
            result = self.client.get_multi(memcache_keys)
            
            # Map back to original keys
            mapped_result = {}
            for memcache_key, value in result.items():
                original_key = key_map.get(memcache_key, memcache_key)
                mapped_result[original_key] = value
            
            return mapped_result
        
        except Exception as e:
            logger.error(f"Error getting many keys: {str(e)}")
            return {}
    
    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in memcached"""
        try:
            # Handle long keys
            memcache_data = {}
            
            for key, value in data.items():
                if len(key) > self.server_max_key_length:
                    key_hash = self._hash_key(key)
                    memcache_data[key_hash] = value
                else:
                    memcache_data[key] = value
            
            return self.client.set_multi(memcache_data, time=ttl or 0)
        
        except Exception as e:
            logger.error(f"Error setting many keys: {str(e)}")
            return False
    
    def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys from memcached"""
        deleted = 0
        for key in keys:
            if self.delete(key):
                deleted += 1
        return deleted
    
    # Statistics
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memcached statistics"""
        try:
            stats = self.client.get_stats()
            if not stats:
                return super().get_stats()
            
            server_stats = {}
            for server, stat_dict in stats:
                server_stats[str(server)] = dict(stat_dict)
            
            total_stats = {
                'service': self.__class__.__name__,
                'timestamp': datetime.utcnow().isoformat(),
                'servers': len(self.servers),
                'server_stats': server_stats
            }
            
            # Aggregate some common stats
            total_connections = 0
            total_items = 0
            total_bytes = 0
            
            for server_stat in server_stats.values():
                total_connections += int(server_stat.get('curr_connections', 0))
                total_items += int(server_stat.get('curr_items', 0))
                total_bytes += int(server_stat.get('bytes', 0))
            
            total_stats.update({
                'total_connections': total_connections,
                'total_items': total_items,
                'total_bytes': total_bytes
            })
            
            return total_stats
        
        except Exception as e:
            logger.error(f"Error getting memcached stats: {str(e)}")
            return super().get_stats()
    
    def health_check(self) -> bool:
        """Health check for memcached"""
        try:
            # Try to get/set a test key
            test_key = f"_health_check_{int(time.time())}"
            test_value = "test"
            
            if not self.set(test_key, test_value, 1):
                return False
            
            retrieved = self.get(test_key)
            self.delete(test_key)
            
            return retrieved == test_value
        
        except Exception as e:
            logger.error(f"Memcached health check failed: {str(e)}")
            return False
    
    # Helper methods
    
    def _hash_key(self, key: str) -> str:
        """Hash long key for memcached"""
        import hashlib
        return hashlib.md5(key.encode()).hexdigest()
    
    def flush_all(self) -> bool:
        """Flush all memcached data"""
        try:
            self.client.flush_all()
            logger.warning("Memcached flushed all data")
            return True
        except Exception as e:
            logger.error(f"Error flushing memcached: {str(e)}")
            return False
    
    def disconnect_all(self) -> None:
        """Disconnect from all memcached servers"""
        try:
            self.client.disconnect_all()
            logger.info("Disconnected from all memcached servers")
        except Exception as e:
            logger.error(f"Error disconnecting from memcached: {str(e)}")
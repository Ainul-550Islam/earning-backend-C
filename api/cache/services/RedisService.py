import redis
import json
import pickle
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime, timedelta
import time
import logging
from .CacheService import CacheService

logger = logging.getLogger(__name__)

class RedisService(CacheService):
    """
    Redis implementation of CacheService
    Supports Redis cluster, sentinel, and single instance
    """
    
    def __init__(
        self, 
        host: str = 'localhost', 
        port: int = 6379, 
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = False,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        max_connections: int = 50,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
        use_cluster: bool = False,
        sentinel_master: Optional[str] = None,
        sentinel_nodes: Optional[List[tuple]] = None
    ):
        """
        Initialize Redis service
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            decode_responses: Whether to decode responses to strings
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Socket connection timeout in seconds
            max_connections: Maximum number of connections in pool
            retry_on_timeout: Whether to retry on timeout
            health_check_interval: Health check interval in seconds
            use_cluster: Whether to use Redis cluster
            sentinel_master: Sentinel master name
            sentinel_nodes: List of sentinel nodes as (host, port) tuples
        """
        self.config = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'decode_responses': decode_responses,
            'socket_timeout': socket_timeout,
            'socket_connect_timeout': socket_connect_timeout,
            'max_connections': max_connections,
            'retry_on_timeout': retry_on_timeout,
            'health_check_interval': health_check_interval
        }
        
        self.use_cluster = use_cluster
        self.sentinel_master = sentinel_master
        self.sentinel_nodes = sentinel_nodes
        
        self._client = None
        self._pubsub = None
        self._subscriptions = {}
        
        self.connect()
    
    def connect(self) -> None:
        """Connect to Redis"""
        try:
            if self.use_cluster:
                from redis.cluster import RedisCluster
                self._client = RedisCluster(
                    host=self.config['host'],
                    port=self.config['port'],
                    password=self.config['password'],
                    decode_responses=self.config['decode_responses'],
                    socket_timeout=self.config['socket_timeout'],
                    socket_connect_timeout=self.config['socket_connect_timeout'],
                    retry_on_timeout=self.config['retry_on_timeout']
                )
            elif self.sentinel_master and self.sentinel_nodes:
                from redis.sentinel import Sentinel
                sentinel = Sentinel(
                    self.sentinel_nodes,
                    socket_timeout=self.config['socket_timeout'],
                    socket_connect_timeout=self.config['socket_connect_timeout']
                )
                self._client = sentinel.master_for(
                    self.sentinel_master,
                    password=self.config['password'],
                    db=self.config['db'],
                    decode_responses=self.config['decode_responses'],
                    socket_timeout=self.config['socket_timeout'],
                    retry_on_timeout=self.config['retry_on_timeout']
                )
            else:
                self._client = redis.Redis(
                    host=self.config['host'],
                    port=self.config['port'],
                    db=self.config['db'],
                    password=self.config['password'],
                    decode_responses=self.config['decode_responses'],
                    socket_timeout=self.config['socket_timeout'],
                    socket_connect_timeout=self.config['socket_connect_timeout'],
                    retry_on_timeout=self.config['retry_on_timeout'],
                    health_check_interval=self.config['health_check_interval'],
                    max_connections=self.config['max_connections']
                )
            
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {self.config['host']}:{self.config['port']}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self._client = None
            raise
    
    @property
    def client(self):
        """Get Redis client with reconnection logic"""
        if self._client is None:
            self.connect()
        
        try:
            # Test connection
            self._client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis connection lost, reconnecting...")
            self.connect()
        
        return self._client
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        try:
            value = self.client.get(key)
            if value is None:
                return None
            
            # Try to deserialize
            try:
                return self._deserialize(value)
            except:
                # Return as-is if can't deserialize
                return value
        
        except Exception as e:
            logger.error(f"Error getting key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis"""
        try:
            serialized = self._serialize(value)
            
            if ttl:
                result = self.client.setex(key, ttl, serialized)
            else:
                result = self.client.set(key, serialized)
            
            return result is True
        
        except Exception as e:
            logger.error(f"Error setting key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            result = self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting key {key}: {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking key {key}: {str(e)}")
            return False
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment integer value in Redis"""
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0
    
    def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement integer value in Redis"""
        try:
            return self.client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {str(e)}")
            return 0
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        try:
            ttl = self.client.ttl(key)
            return ttl if ttl >= 0 else -1
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {str(e)}")
            return -1
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        try:
            return self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Error setting expire for key {key}: {str(e)}")
            return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        try:
            return self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {str(e)}")
            return []
    
    # Advanced Redis operations
    
    def hget(self, hash_key: str, field: str) -> Optional[Any]:
        """Get field from Redis hash"""
        try:
            value = self.client.hget(hash_key, field)
            if value is None:
                return None
            
            try:
                return self._deserialize(value)
            except:
                return value
        
        except Exception as e:
            logger.error(f"Error getting hash field {hash_key}.{field}: {str(e)}")
            return None
    
    def hset(self, hash_key: str, field: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set field in Redis hash"""
        try:
            serialized = self._serialize(value)
            result = self.client.hset(hash_key, field, serialized)
            
            # Set TTL for the entire hash if specified
            if ttl and result:
                self.client.expire(hash_key, ttl)
            
            return result >= 0
        
        except Exception as e:
            logger.error(f"Error setting hash field {hash_key}.{field}: {str(e)}")
            return False
    
    def hgetall(self, hash_key: str) -> Dict[str, Any]:
        """Get all fields from Redis hash"""
        try:
            result = self.client.hgetall(hash_key)
            deserialized = {}
            
            for key, value in result.items():
                try:
                    deserialized[key] = self._deserialize(value)
                except:
                    deserialized[key] = value
            
            return deserialized
        
        except Exception as e:
            logger.error(f"Error getting all hash fields {hash_key}: {str(e)}")
            return {}
    
    def hdel(self, hash_key: str, fields: List[str]) -> int:
        """Delete fields from Redis hash"""
        try:
            return self.client.hdel(hash_key, *fields)
        except Exception as e:
            logger.error(f"Error deleting hash fields {hash_key}: {str(e)}")
            return 0
    
    def sadd(self, set_key: str, *members: Any) -> int:
        """Add members to Redis set"""
        try:
            serialized_members = [self._serialize(member) for member in members]
            return self.client.sadd(set_key, *serialized_members)
        except Exception as e:
            logger.error(f"Error adding to set {set_key}: {str(e)}")
            return 0
    
    def srem(self, set_key: str, *members: Any) -> int:
        """Remove members from Redis set"""
        try:
            serialized_members = [self._serialize(member) for member in members]
            return self.client.srem(set_key, *serialized_members)
        except Exception as e:
            logger.error(f"Error removing from set {set_key}: {str(e)}")
            return 0
    
    def smembers(self, set_key: str) -> set:
        """Get all members of Redis set"""
        try:
            members = self.client.smembers(set_key)
            deserialized = set()
            
            for member in members:
                try:
                    deserialized.add(self._deserialize(member))
                except:
                    deserialized.add(member)
            
            return deserialized
        
        except Exception as e:
            logger.error(f"Error getting set members {set_key}: {str(e)}")
            return set()
    
    # Pub/Sub operations
    
    def publish(self, channel: str, message: Any) -> bool:
        """Publish message to Redis channel"""
        try:
            serialized = self._serialize(message)
            result = self.client.publish(channel, serialized)
            return result > 0
        except Exception as e:
            logger.error(f"Error publishing to channel {channel}: {str(e)}")
            return False
    
    def subscribe(self, channel: str, callback: Callable) -> None:
        """Subscribe to Redis channel"""
        try:
            if self._pubsub is None:
                self._pubsub = self.client.pubsub()
            
            def message_handler(message):
                if message['type'] == 'message':
                    try:
                        data = self._deserialize(message['data'])
                    except:
                        data = message['data']
                    callback(data)
            
            self._pubsub.subscribe(**{channel: message_handler})
            self._subscriptions[channel] = callback
            
            # Start listening in background thread
            import threading
            thread = threading.Thread(target=self._pubsub.run_in_thread, daemon=True)
            thread.start()
            
            logger.info(f"Subscribed to Redis channel: {channel}")
        
        except Exception as e:
            logger.error(f"Error subscribing to channel {channel}: {str(e)}")
    
    def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from Redis channel"""
        try:
            if self._pubsub and channel in self._subscriptions:
                self._pubsub.unsubscribe(channel)
                del self._subscriptions[channel]
                logger.info(f"Unsubscribed from Redis channel: {channel}")
        except Exception as e:
            logger.error(f"Error unsubscribing from channel {channel}: {str(e)}")
    
    # Pipeline operations
    
    def pipeline(self):
        """Get Redis pipeline for batch operations"""
        return self.client.pipeline()
    
    # Lua scripting
    def register_script(self, script: str):
        """Register Lua script"""
        return self.client.register_script(script)
    
    # Statistics
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        try:
            info = self.client.info()
            stats = super().get_stats()
            stats.update({
                'redis_version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'used_memory': info.get('used_memory_human'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'uptime_in_seconds': info.get('uptime_in_seconds'),
                'role': info.get('role', 'unknown')
            })
            return stats
        except Exception as e:
            logger.error(f"Error getting Redis stats: {str(e)}")
            return super().get_stats()
    
    def flush_all(self) -> bool:
        """Flush all Redis data (use with caution!)"""
        try:
            self.client.flushall()
            logger.warning("Redis flushed all data")
            return True
        except Exception as e:
            logger.error(f"Error flushing Redis: {str(e)}")
            return False
    
    def close(self) -> None:
        """Close Redis connection"""
        try:
            if self._pubsub:
                self._pubsub.close()
            
            if self._client:
                self._client.close()
            
            self._client = None
            self._pubsub = None
            logger.info("Redis connection closed")
        
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
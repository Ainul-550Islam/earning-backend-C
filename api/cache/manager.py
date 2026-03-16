"""
Cache Manager - Centralized cache service management
"""

import os
from typing import Dict, Any, Optional
# from dotenv import load_dotenv

# load_dotenv()

class CacheManager:
    """
    Central manager for all cache services
    Provides unified interface and configuration
    """
    
    _instance = None
    _services = {}
    _default_backend = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._load_configuration()
            self._initialize_services()
    
    def _load_configuration(self):
        """Load cache configuration from environment - Bulletproof version"""
        import os
        # Try every possible way to get Redis URL
        redis_url = (
            os.environ.get('REDIS_URL') or
            os.environ.get('redis_url') or
            None
        )
        print(f"[CACHE MANAGER] REDIS_URL={redis_url}")
        print(f"[CACHE MANAGER] ENV KEYS WITH REDIS: {[k for k in os.environ if 'REDIS' in k.upper()]}")

        if redis_url:
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            redis_host = parsed.hostname or 'localhost'
            redis_port = parsed.port or 6379
            redis_db = int((parsed.path or '/0').lstrip('/') or 0)
            redis_password = parsed.password
        else:
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_db = int(os.environ.get('REDIS_DB', 0))
            redis_password = os.environ.get('REDIS_PASSWORD')
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

        print(f"[CACHE MANAGER] Final REDIS host={redis_host} port={redis_port}")

        self.config = {
            'default_backend': os.environ.get('CACHE_BACKEND', 'redis'),
            'redis': {
                'host': redis_host,
                'port': redis_port,
                'db': redis_db,
                'password': redis_password,
                'url': redis_url,
                'decode_responses': os.environ.get('REDIS_DECODE_RESPONSES', 'False').lower() == 'true',
                'max_connections': int(os.environ.get('REDIS_MAX_CONNECTIONS', 50)),
                'use_cluster': os.environ.get('REDIS_CLUSTER', 'False').lower() == 'true',
                'sentinel_master': os.environ.get('REDIS_SENTINEL_MASTER'),
                'sentinel_nodes': self._parse_sentinel_nodes(os.environ.get('REDIS_SENTINEL_NODES'))
            },
            'memcached': {
                'servers': os.environ.get('MEMCACHED_SERVERS', 'localhost:11211').split(','),
            },
            'lru': {
                'max_size': int(os.environ.get('LRU_CACHE_SIZE', 1000)),
                'default_ttl': int(os.environ.get('LRU_CACHE_TTL', 300))
            },
            'ttl': {
                'max_size': int(os.environ.get('TTL_CACHE_SIZE', 1000)),
                'default_ttl': int(os.environ.get('TTL_CACHE_TTL', 300))
            }
        }
        self._default_backend = self.config['default_backend']


    def _parse_sentinel_nodes(self, nodes_str: Optional[str]) -> Optional[list]:
        """Parse Redis sentinel nodes from string"""
        if not nodes_str:
            return None
        
        nodes = []
        for node in nodes_str.split(','):
            host, port = node.strip().split(':')
            nodes.append((host, int(port)))
        
        return nodes
    
    def _initialize_services(self):
        """Initialize cache services"""
        # Initialize based on configuration
        backend = self.config['default_backend']
        
        if backend == 'redis':
            self._initialize_redis()
        elif backend == 'memcached':
            self._initialize_memcached()
        elif backend == 'lru':
            self._initialize_lru()
        elif backend == 'ttl':
            self._initialize_ttl()
        
        # Set default service
        self._services['default'] = self._services.get(backend)
    
    def _initialize_redis(self):
        """Initialize Redis service"""
        try:
            from .services import RedisService
            
            redis_config = self.config['redis']
            import os
            redis_url = redis_config.get('url') or os.environ.get('REDIS_URL')
            if redis_url:
                import redis as redis_lib
                client = redis_lib.from_url(redis_url, decode_responses=redis_config['decode_responses'])
                redis_service = RedisService(
                    host=redis_config['host'],
                    port=redis_config['port'],
                    db=redis_config['db'],
                    password=redis_config['password'],
                    decode_responses=redis_config['decode_responses'],
                    max_connections=redis_config['max_connections'],
                )
                redis_service._client = client
                client.ping()
                print(f"[CACHE MANAGER] Redis connected via URL!")
            else:
                redis_service = RedisService(
                    host=redis_config['host'],
                    port=redis_config['port'],
                    db=redis_config['db'],
                    password=redis_config['password'],
                    decode_responses=redis_config['decode_responses'],
                    max_connections=redis_config['max_connections'],
                    use_cluster=redis_config['use_cluster'],
                    sentinel_master=redis_config['sentinel_master'],
                    sentinel_nodes=redis_config['sentinel_nodes']
                )
            
            self._services['redis'] = redis_service
            print("Redis cache service initialized")
            
        except Exception as e:
            print(f"Failed to initialize Redis: {str(e)}")
            # Fall back to LRU cache
            self._initialize_lru()
            self._default_backend = 'lru'
    
    def _initialize_memcached(self):
        """Initialize Memcached service"""
        try:
            from .services import MemcachedService
            
            memcached_config = self.config['memcached']
            memcached_service = MemcachedService(
                servers=memcached_config['servers'],
                debug=memcached_config['debug'],
                socket_timeout=memcached_config['socket_timeout'],
                connect_timeout=memcached_config['connect_timeout']
            )
            
            self._services['memcached'] = memcached_service
            print("Memcached service initialized")
            
        except Exception as e:
            print(f"Failed to initialize Memcached: {str(e)}")
            # Fall back to LRU cache
            self._initialize_lru()
            self._default_backend = 'lru'
    
    def _initialize_lru(self):
        """Initialize LRU cache service"""
        from .strategies import LRUCacheService
        
        lru_config = self.config['lru']
        lru_service = LRUCacheService(
            max_size=lru_config['max_size'],
            default_ttl=lru_config['default_ttl']
        )
        
        self._services['lru'] = lru_service
        print("LRU cache service initialized")
    
    def _initialize_ttl(self):
        """Initialize TTL cache service"""
        from .strategies import TTLCacheService
        
        ttl_config = self.config['ttl']
        ttl_service = TTLCacheService(
            max_size=ttl_config['max_size'],
            default_ttl=ttl_config['default_ttl']
        )
        
        self._services['ttl'] = ttl_service
        print("TTL cache service initialized")
    
    def get_cache(self, backend: Optional[str] = None) -> Any:
        """
        Get cache service instance
        
        Args:
            backend: Cache backend name ('redis', 'memcached', 'lru', 'ttl')
        
        Returns:
            Cache service instance
        """
        backend = backend or self._default_backend
        
        if backend not in self._services:
            # Try to initialize if not exists
            if backend == 'redis':
                self._initialize_redis()
            elif backend == 'memcached':
                self._initialize_memcached()
            elif backend == 'lru':
                self._initialize_lru()
            elif backend == 'ttl':
                self._initialize_ttl()
            else:
                raise ValueError(f"Unknown cache backend: {backend}")
        
        return self._services.get(backend)
    
    def set_default_backend(self, backend: str):
        """Set default cache backend"""
        if backend not in ['redis', 'memcached', 'lru', 'ttl']:
            raise ValueError(f"Invalid backend: {backend}")
        
        self._default_backend = backend
        self._services['default'] = self._services.get(backend)
    
    def register_service(self, name: str, service: Any):
        """Register custom cache service"""
        self._services[name] = service
    
    def unregister_service(self, name: str):
        """Unregister cache service"""
        if name in self._services:
            # Close service if it has close method
            if hasattr(self._services[name], 'close'):
                self._services[name].close()
            
            del self._services[name]
    
    def get_all_services(self) -> Dict[str, Any]:
        """Get all registered cache services"""
        return self._services.copy()
    
    def health_check(self, backend: Optional[str] = None) -> bool:
        """Health check for cache service"""
        try:
            service = self.get_cache(backend)
            if hasattr(service, 'health_check'):
                return service.health_check()
            return True
        except Exception:
            return False
    
    def get_stats(self, backend: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for cache service"""
        try:
            service = self.get_cache(backend)
            if hasattr(service, 'get_stats'):
                return service.get_stats()
            return {'status': 'unknown'}
        except Exception as e:
            return {'error': str(e), 'status': 'unavailable'}
    
    def close_all(self):
        """Close all cache services"""
        for name, service in self._services.items():
            try:
                if hasattr(service, 'close'):
                    service.close()
                print(f"Closed cache service: {name}")
            except Exception as e:
                print(f"Error closing cache service {name}: {str(e)}")
        
        self._services.clear()
        self._initialized = False


# Global cache manager instance
cache_manager = CacheManager()

# Convenience functions
def get_cache(backend: Optional[str] = None) -> Any:
    """Get cache service instance"""
    return cache_manager.get_cache(backend)

def health_check(backend: Optional[str] = None) -> bool:
    """Health check for cache service"""
    return cache_manager.health_check(backend)

def get_stats(backend: Optional[str] = None) -> Dict[str, Any]:
    """Get cache statistics"""
    return cache_manager.get_stats(backend)

def close_all():
    """Close all cache services"""
    cache_manager.close_all()
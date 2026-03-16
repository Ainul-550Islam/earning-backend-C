import functools
import inspect
import hashlib
import json
from typing import Callable, Any, Optional, Dict, List, Union, TypeVar
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')

class cache_data:
    """
    General-purpose data caching decorator
    Can cache any function's return value
    """
    
    def __init__(
        self,
        timeout: int = 300,
        key_prefix: str = "",
        key_func: Optional[Callable] = None,
        condition: Optional[Callable] = None,
        unless: Optional[Callable] = None,
        cache_none: bool = True,
        cache_exceptions: bool = False,
        invalidate_on: List[str] = None,
        version: int = 1,
        cache_backend: str = "default"
    ):
        """
        Args:
            timeout: Cache timeout in seconds
            key_prefix: Prefix for cache key
            key_func: Function to generate cache key from args/kwargs
            condition: Callable that returns bool to determine if should cache
            unless: Callable that returns bool to determine if should NOT cache
            cache_none: Whether to cache None return values
            cache_exceptions: Whether to cache exception results
            invalidate_on: List of events that should invalidate this cache
            version: Cache version (for cache invalidation)
            cache_backend: Cache backend to use
        """
        self.timeout = timeout
        self.key_prefix = key_prefix
        self.key_func = key_func
        self.condition = condition
        self.unless = unless
        self.cache_none = cache_none
        self.cache_exceptions = cache_exceptions
        self.invalidate_on = invalidate_on or []
        self.version = version
        self.cache_backend = cache_backend
        
        # Get cache service
        from api.cache.manager import cache_manager
        self.cache_service = cache_manager.get_cache(self.cache_backend)
        
        # Get cache invalidator if needed
        if self.invalidate_on:
            from api.cache.services import CacheInvalidator
            self.invalidator = CacheInvalidator(self.cache_service)
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator implementation"""
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if should cache
            if not self._should_cache(args, kwargs):
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = self._generate_key(func, args, kwargs)
            
            # Try to get from cache
            cached_result = self._get_cached(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Cache miss - execute function
            logger.debug(f"Cache miss for {func.__name__}")
            try:
                result = func(*args, **kwargs)
                exception = None
            except Exception as e:
                result = None
                exception = e
            
            # Cache the result
            if self._should_cache_result(result, exception):
                self._cache_result(cache_key, result, exception)
            
            # Re-raise exception if occurred
            if exception:
                raise exception
            
            return result
        
        return wrapper
    
    def _should_cache(self, args: tuple, kwargs: dict) -> bool:
        """Determine if should cache this call"""
        # Check condition
        if self.condition and not self.condition(*args, **kwargs):
            return False
        
        # Check unless
        if self.unless and self.unless(*args, **kwargs):
            return False
        
        return True
    
    def _should_cache_result(self, result: Any, exception: Optional[Exception]) -> bool:
        """Determine if result should be cached"""
        # Don't cache exceptions unless configured
        if exception and not self.cache_exceptions:
            return False
        
        # Check if result is None
        if result is None and not self.cache_none:
            return False
        
        return True
    
    def _generate_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Generate cache key"""
        if self.key_func:
            return self.key_func(*args, **kwargs)
        
        # Default key generation
        key_parts = [self.key_prefix or "func", func.__module__, func.__name__]
        
        # Add version
        key_parts.append(f"v{self.version}")
        
        # Add args (skip self for methods)
        if args and hasattr(args[0], '__class__') and args[0].__class__.__name__ == func.__name__.split('.')[0]:
            # Skip self argument for instance methods
            args = args[1:]
        
        if args:
            args_hash = hashlib.md5(str(args).encode()).hexdigest()[:12]
            key_parts.append(f"args:{args_hash}")
        
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:12]
            key_parts.append(f"kwargs:{kwargs_hash}")
        
        return ":".join(str(part) for part in key_parts)
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached result"""
        try:
            cached = self.cache_service.get(cache_key)
            if cached:
                # Check if it's an exception result
                if isinstance(cached, dict) and cached.get('_type') == 'exception':
                    # Re-raise cached exception
                    import pickle
                    exception = pickle.loads(cached['exception'])
                    raise exception
                
                return cached
        except Exception as e:
            logger.error(f"Error getting cached result: {str(e)}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Any, exception: Optional[Exception] = None):
        """Cache result"""
        try:
            if exception and self.cache_exceptions:
                # Cache exception
                import pickle
                cache_data = {
                    '_type': 'exception',
                    'exception': pickle.dumps(exception),
                    'cached_at': datetime.utcnow().isoformat()
                }
            else:
                cache_data = result
            
            self.cache_service.set(cache_key, cache_data, self.timeout)
            
            # Register for invalidation if needed
            if self.invalidate_on:
                self._register_invalidation(cache_key)
                
        except Exception as e:
            logger.error(f"Error caching result: {str(e)}")
    
    def _register_invalidation(self, cache_key: str):
        """Register cache key for invalidation"""
        for event in self.invalidate_on:
            self.invalidator.add_dependency(event, cache_key)
    
    def invalidate(self, *args, **kwargs):
        """Invalidate cache for this function"""
        cache_key = self._generate_key(self, args, kwargs)
        self.cache_service.delete(cache_key)
        logger.debug(f"Invalidated cache for {self.__name__}")

# Specialized decorators
def cache_property(timeout: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching property getters
    """
    def decorator(func):
        @property
        @functools.wraps(func)
        def wrapper(self):
            # Generate cache key
            if key_prefix:
                cache_key = f"{key_prefix}:{self.__class__.__name__}:{func.__name__}:{id(self)}"
            else:
                cache_key = f"property:{self.__class__.__name__}:{func.__name__}:{id(self)}"
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            
            # Try to get from cache
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Cache miss - calculate property
            result = func(self)
            
            # Cache the result
            cache_service.set(cache_key, result, timeout)
            
            return result
        
        # Add invalidate method
        def invalidate(self):
            cache_key = f"property:{self.__class__.__name__}:{func.__name__}:{id(self)}"
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            cache_service.delete(cache_key)
        
        wrapper.invalidate = invalidate
        return wrapper
    
    return decorator

def cache_method_result(
    timeout: int = 300,
    key_func: Optional[Callable] = None,
    cache_none: bool = True
):
    """
    Decorator for caching instance method results
    """
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(self, *args, **kwargs)
            else:
                key_parts = [
                    "method",
                    self.__class__.__name__,
                    method.__name__,
                    str(id(self))
                ]
                
                if args:
                    args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                    key_parts.append(f"args:{args_hash}")
                
                if kwargs:
                    sorted_kwargs = sorted(kwargs.items())
                    kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                    key_parts.append(f"kwargs:{kwargs_hash}")
                
                cache_key = ":".join(key_parts)
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            
            # Try to get from cache
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Cache miss - execute method
            result = method(self, *args, **kwargs)
            
            # Cache the result
            if result is not None or cache_none:
                cache_service.set(cache_key, result, timeout)
            
            return result
        
        # Add invalidate method
        def invalidate(self, *args, **kwargs):
            if key_func:
                cache_key = key_func(self, *args, **kwargs)
            else:
                key_parts = [
                    "method",
                    self.__class__.__name__,
                    method.__name__,
                    str(id(self))
                ]
                
                if args:
                    args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                    key_parts.append(f"args:{args_hash}")
                
                if kwargs:
                    sorted_kwargs = sorted(kwargs.items())
                    kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                    key_parts.append(f"kwargs:{kwargs_hash}")
                
                cache_key = ":".join(key_parts)
            
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            cache_service.delete(cache_key)
        
        wrapper.invalidate = invalidate
        return wrapper
    
    return decorator

def cache_class_method(
    timeout: int = 300,
    key_prefix: str = ""
):
    """
    Decorator for caching classmethod results
    """
    def decorator(method):
        @classmethod
        @functools.wraps(method)
        def wrapper(cls, *args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or "classmethod", cls.__name__, method.__name__]
            
            if args:
                args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                key_parts.append(f"args:{args_hash}")
            
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                key_parts.append(f"kwargs:{kwargs_hash}")
            
            cache_key = ":".join(key_parts)
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            
            # Try to get from cache
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Cache miss - execute method
            result = method(cls, *args, **kwargs)
            
            # Cache the result
            cache_service.set(cache_key, result, timeout)
            
            return result
        
        # Add invalidate method
        @classmethod
        def invalidate(cls, *args, **kwargs):
            key_parts = [key_prefix or "classmethod", cls.__name__, method.__name__]
            
            if args:
                args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                key_parts.append(f"args:{args_hash}")
            
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                key_parts.append(f"kwargs:{kwargs_hash}")
            
            cache_key = ":".join(key_parts)
            
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            cache_service.delete(cache_key)
        
        wrapper.invalidate = invalidate
        return wrapper
    
    return decorator

def cache_static_method(
    timeout: int = 300,
    key_prefix: str = ""
):
    """
    Decorator for caching staticmethod results
    """
    def decorator(method):
        @staticmethod
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or "staticmethod", method.__name__]
            
            if args:
                args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                key_parts.append(f"args:{args_hash}")
            
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                key_parts.append(f"kwargs:{kwargs_hash}")
            
            cache_key = ":".join(key_parts)
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            
            # Try to get from cache
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Cache miss - execute method
            result = method(*args, **kwargs)
            
            # Cache the result
            cache_service.set(cache_key, result, timeout)
            
            return result
        
        # Add invalidate method
        @staticmethod
        def invalidate(*args, **kwargs):
            key_parts = [key_prefix or "staticmethod", method.__name__]
            
            if args:
                args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
                key_parts.append(f"args:{args_hash}")
            
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                kwargs_hash = hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]
                key_parts.append(f"kwargs:{kwargs_hash}")
            
            cache_key = ":".join(key_parts)
            
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            cache_service.delete(cache_key)
        
        wrapper.invalidate = invalidate
        return wrapper
    
    return decorator

# Cache with rate limiting
def cached_with_rate_limit(
    timeout: int = 300,
    calls_per_period: int = 100,
    period: int = 60,
    key_prefix: str = ""
):
    """
    Cache with rate limiting
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate rate limit key
            rate_key = f"rate:{key_prefix or func.__name__}:{int(time.time() // period)}"
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            
            # Check rate limit
            current_calls = cache_service.get(rate_key) or 0
            if current_calls >= calls_per_period:
                # Rate limit exceeded - use cache or return default
                cache_key = f"cache:{key_prefix or func.__name__}:{hashlib.md5(str(args) + str(kwargs)).hexdigest()[:16]}"
                cached = cache_service.get(cache_key)
                if cached is not None:
                    return cached
                else:
                    # Return cached default or raise exception
                    raise Exception("Rate limit exceeded")
            
            # Increment rate counter
            cache_service.increment(rate_key, 1)
            cache_service.expire(rate_key, period)
            
            # Generate cache key
            cache_key = f"cache:{key_prefix or func.__name__}:{hashlib.md5(str(args) + str(kwargs)).hexdigest()[:16]}"
            
            # Try to get from cache
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Cache miss - execute function
            result = func(*args, **kwargs)
            
            # Cache the result
            cache_service.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    
    return decorator
import functools
import hashlib
import json
from typing import Callable, Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import logging
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache as django_cache
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

class cache_page:
    """
    Full page caching decorator
    Caches entire HTML page output
    """
    
    def __init__(
        self,
        timeout: int = 3600,
        key_prefix: str = "",
        cache_by_user: bool = False,
        cache_by_language: bool = True,
        cache_by_device: bool = False,
        vary_on_headers: List[str] = None,
        cache_anonymous_only: bool = True,
        cache_condition: Callable[[HttpRequest], bool] = None,
        cache_backend: str = "default"
    ):
        """
        Args:
            timeout: Cache timeout in seconds
            key_prefix: Prefix for cache key
            cache_by_user: Whether to cache separately per user
            cache_by_language: Whether to cache separately per language
            cache_by_device: Whether to cache separately per device
            vary_on_headers: List of headers to vary cache on
            cache_anonymous_only: Cache only for anonymous users
            cache_condition: Callable that returns bool to determine if should cache
            cache_backend: Cache backend to use
        """
        self.timeout = timeout
        self.key_prefix = key_prefix
        self.cache_by_user = cache_by_user
        self.cache_by_language = cache_by_language
        self.cache_by_device = cache_by_device
        self.vary_on_headers = vary_on_headers or []
        self.cache_anonymous_only = cache_anonymous_only
        self.cache_condition = cache_condition
        self.cache_backend = cache_backend
        
        # Get cache service
        from api.cache.manager import cache_manager
        self.cache_service = cache_manager.get_cache(self.cache_backend)
    
    def __call__(self, view_func: Callable) -> Callable:
        """Decorator implementation"""
        
        @functools.wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            # Check if should cache
            if not self._should_cache(request):
                return view_func(request, *args, **kwargs)
            
            # Generate cache key
            cache_key = self._generate_page_cache_key(request)
            
            # Try to get from cache
            cached_page = self._get_cached_page(cache_key)
            if cached_page is not None:
                logger.debug(f"Page cache hit: {request.path}")
                
                # Create response from cache
                response = HttpResponse(
                    cached_page['content'],
                    content_type=cached_page.get('content_type', 'text/html')
                )
                
                # Add cache headers
                response['X-Page-Cache'] = 'HIT'
                response['X-Cache-Timestamp'] = cached_page.get('cached_at', '')
                response['X-Cache-Expires'] = cached_page.get('expires_at', '')
                
                # Add original headers
                for key, value in cached_page.get('headers', {}).items():
                    if key not in ['X-Page-Cache', 'X-Cache-Timestamp', 'X-Cache-Expires']:
                        response[key] = value
                
                return response
            
            # Cache miss - execute view
            logger.debug(f"Page cache miss: {request.path}")
            response = view_func(request, *args, **kwargs)
            
            # Cache the response if successful
            if self._should_cache_response(response):
                self._cache_page(cache_key, response)
                response['X-Page-Cache'] = 'MISS'
            
            return response
        
        return _wrapped_view
    
    def _should_cache(self, request: HttpRequest) -> bool:
        """Determine if page should be cached"""
        # Only cache GET requests
        if request.method != 'GET':
            return False
        
        # Don't cache AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
        
        # Check cache condition
        if self.cache_condition and not self.cache_condition(request):
            return False
        
        # Check anonymous only
        if self.cache_anonymous_only and request.user.is_authenticated:
            return False
        
        # Don't cache if request has cache-control: no-cache
        cache_control = request.META.get('HTTP_CACHE_CONTROL', '')
        if 'no-cache' in cache_control or 'no-store' in cache_control:
            return False
        
        # Don't cache if user is logged in and we're not caching by user
        if request.user.is_authenticated and not self.cache_by_user:
            return False
        
        return True
    
    def _should_cache_response(self, response: HttpResponse) -> bool:
        """Determine if response should be cached"""
        # Only cache successful HTML responses
        if response.status_code != 200:
            return False
        
        # Check content type
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return False
        
        # Check response cache-control headers
        cache_control = response.get('Cache-Control', '')
        if 'no-store' in cache_control or 'private' in cache_control:
            return False
        
        # Don't cache if response has Set-Cookie header (session changes)
        if response.has_header('Set-Cookie'):
            return False
        
        return True
    
    def _generate_page_cache_key(self, request: HttpRequest) -> str:
        """Generate cache key for page"""
        key_parts = [self.key_prefix or "page"]
        
        # Add path
        key_parts.append(request.path)
        
        # Add query parameters (sorted)
        if request.GET:
            sorted_params = sorted(request.GET.items())
            param_hash = hashlib.md5(str(sorted_params).encode()).hexdigest()[:12]
            key_parts.append(f"q:{param_hash}")
        
        # Add language
        if self.cache_by_language:
            language = getattr(request, 'LANGUAGE_CODE', 'en')
            key_parts.append(f"lang:{language}")
        
        # Add user
        if self.cache_by_user and request.user.is_authenticated:
            key_parts.append(f"user:{request.user.id}")
        
        # Add device type
        if self.cache_by_device:
            device_type = self._get_device_type(request)
            key_parts.append(f"device:{device_type}")
        
        # Add headers
        for header in self.vary_on_headers:
            header_value = request.META.get(f'HTTP_{header.upper().replace("-", "_")}')
            if header_value:
                key_parts.append(f"{header}:{header_value[:20]}")
        
        # Add cookie for authenticated users
        if request.user.is_authenticated and hasattr(request, 'session'):
            session_key = request.session.session_key
            if session_key:
                key_parts.append(f"session:{session_key[:8]}")
        
        return ":".join(str(part) for part in key_parts)
    
    def _get_device_type(self, request: HttpRequest) -> str:
        """Detect device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'
    
    def _get_cached_page(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached page from cache service"""
        try:
            return self.cache_service.get(cache_key)
        except Exception as e:
            logger.error(f"Error getting cached page: {str(e)}")
            return None
    
    def _cache_page(self, cache_key: str, response: HttpResponse):
        """Cache page in cache service"""
        try:
            # Calculate expiry time
            cached_at = datetime.utcnow()
            expires_at = cached_at + timedelta(seconds=self.timeout)
            
            # Prepare cache data
            cache_data = {
                'content': response.content.decode('utf-8') if isinstance(response.content, bytes) else response.content,
                'content_type': response.get('Content-Type', 'text/html'),
                'cached_at': cached_at.isoformat(),
                'expires_at': expires_at.isoformat(),
                'headers': dict(response.headers)
            }
            
            # Store in cache
            self.cache_service.set(cache_key, cache_data, self.timeout)
            logger.debug(f"Page cached: {cache_key}")
            
        except Exception as e:
            logger.error(f"Error caching page: {str(e)}")

# Vary decorators for more control
def vary_on_cookie(view_func=None, cookies=None):
    """
    Decorator to vary cache on cookies
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # This would be integrated with cache_page
            return func(request, *args, **kwargs)
        return wrapper
    
    if view_func:
        return decorator(view_func)
    return decorator

def vary_on_headers(view_func=None, headers=None):
    """
    Decorator to vary cache on headers
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # This would be integrated with cache_page
            return func(request, *args, **kwargs)
        return wrapper
    
    if view_func:
        return decorator(view_func)
    return decorator

def vary_on_user(view_func=None):
    """
    Decorator to vary cache on user
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # This would be integrated with cache_page
            return func(request, *args, **kwargs)
        return wrapper
    
    if view_func:
        return decorator(view_func)
    return decorator

# Template fragment caching
def cache_template_fragment(
    fragment_name: str,
    timeout: int = 3600,
    vary_on: List[str] = None,
    cache_backend: str = "default"
):
    """
    Cache template fragment decorator
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key for fragment
            key_parts = ["fragment", fragment_name]
            
            if vary_on:
                for vary in vary_on:
                    if vary == 'user' and request.user.is_authenticated:
                        key_parts.append(f"user:{request.user.id}")
                    elif vary == 'language':
                        language = getattr(request, 'LANGUAGE_CODE', 'en')
                        key_parts.append(f"lang:{language}")
                    # Add more vary conditions as needed
            
            cache_key = ":".join(key_parts)
            
            # Get cache service
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache(cache_backend)
            
            # Try to get from cache
            cached_fragment = cache_service.get(cache_key)
            if cached_fragment is not None:
                return cached_fragment
            
            # Cache miss - execute function
            fragment = func(request, *args, **kwargs)
            
            # Cache the fragment
            cache_service.set(cache_key, fragment, timeout)
            
            return fragment
        
        return wrapper
    return decorator

# Middleware for automatic page caching
class PageCacheMiddleware:
    """
    Middleware for automatic page caching
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_pages = {}
        
        # Load cache configuration
        self._load_cache_config()
        
        from api.cache.manager import cache_manager
        self.cache_service = cache_manager.get_cache('default')
    
    def _load_cache_config(self):
        """Load page cache configuration"""
        # This could be from settings or database
        self.cache_pages = {
            '/': {'timeout': 300, 'vary_on_user': False},
            '/offers/': {'timeout': 60, 'vary_on_user': True},
            '/tasks/': {'timeout': 30, 'vary_on_user': True},
            '/leaderboard/': {'timeout': 60, 'vary_on_user': False},
            # Add more pages as needed
        }
    
    def __call__(self, request):
        # Check if this path should be cached
        cache_config = None
        for path, config in self.cache_pages.items():
            if request.path.startswith(path):
                cache_config = config
                break
        
        if not cache_config:
            return self.get_response(request)
        
        # Create cache decorator with config
        cache_decorator = cache_page(
            timeout=cache_config.get('timeout', 300),
            cache_by_user=cache_config.get('vary_on_user', False),
            cache_anonymous_only=cache_config.get('cache_anonymous_only', True)
        )
        
        # Check if should cache
        if not cache_decorator._should_cache(request):
            return self.get_response(request)
        
        # Generate cache key
        cache_key = cache_decorator._generate_page_cache_key(request)
        
        # Try to get from cache
        cached_page = self.cache_service.get(cache_key)
        if cached_page is not None:
            response = HttpResponse(
                cached_page['content'],
                content_type=cached_page.get('content_type', 'text/html')
            )
            response['X-Page-Cache'] = 'HIT'
            response['X-Cache-Timestamp'] = cached_page.get('cached_at', '')
            return response
        
        # Cache miss
        response = self.get_response(request)
        
        # Cache if successful
        if response.status_code == 200 and 'text/html' in response.get('Content-Type', ''):
            cache_decorator._cache_page(cache_key, response)
            response['X-Page-Cache'] = 'MISS'
        
        return response
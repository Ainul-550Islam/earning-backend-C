# api/cache/middleware.py
"""
Cache middleware for global caching.
- PageCacheMiddleware: Full page caching for configured paths
- CacheControlMiddleware: Adds Cache-Control headers for cacheable responses
- RequestCacheMiddleware: Per-request in-memory cache (avoid duplicate queries)
"""
import logging
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class PageCacheMiddleware:
    """
    Middleware for automatic page caching.
    Uses Redis/Memcached via cache_manager.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_pages = {}
        self._load_cache_config()
        try:
            from api.cache.manager import cache_manager
            self.cache_service = cache_manager.get_cache('default')
        except Exception as e:
            logger.debug(f"Cache service not available: {e}")
            self.cache_service = None
    
    def _load_cache_config(self):
        """Load page cache configuration (paths to cache)."""
        self.cache_pages = {
            '/': {'timeout': 300, 'vary_on_user': False},
            '/offers/': {'timeout': 60, 'vary_on_user': True},
            '/tasks/': {'timeout': 30, 'vary_on_user': True},
            '/leaderboard/': {'timeout': 60, 'vary_on_user': False},
            '/api/': {'timeout': 60, 'vary_on_user': True},
        }
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        from api.cache.decorators.cache_page import cache_page
        from django.http import HttpResponse
        
        cache_config = None
        for path, config in self.cache_pages.items():
            if request.path.startswith(path.rstrip('/')) or (path == '/' and request.path == '/'):
                cache_config = config
                break
        
        if not cache_config:
            return self.get_response(request)
        
        # If cache backend not available, skip caching logic
        if not self.cache_service:
            return self.get_response(request)

        cache_decorator = cache_page(
            timeout=cache_config.get('timeout', 300),
            cache_by_user=cache_config.get('vary_on_user', False),
            cache_anonymous_only=cache_config.get('cache_anonymous_only', True)
        )
        
        if not cache_decorator._should_cache(request):
            return self.get_response(request)
        
        cache_key = cache_decorator._generate_page_cache_key(request)
        cached_page = self.cache_service.get(cache_key)
        
        if cached_page is not None:
            response = HttpResponse(
                cached_page['content'],
                content_type=cached_page.get('content_type', 'text/html')
            )
            response['X-Page-Cache'] = 'HIT'
            response['X-Cache-Timestamp'] = cached_page.get('cached_at', '')
            return response
        
        response = self.get_response(request)
        if response.status_code == 200 and 'text/html' in response.get('Content-Type', ''):
            cache_decorator._cache_page(cache_key, response)
            response['X-Page-Cache'] = 'MISS'
        
        return response


class CacheControlMiddleware:
    """
    Adds Cache-Control headers for cacheable API responses.
    Configure CACHE_CONTROL_PATHS in settings.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        
        # Only add headers for GET/HEAD
        if request.method not in ('GET', 'HEAD'):
            return response
        
        # Check if path should have cache headers
        path = request.path
        if path.startswith('/api/') and response.status_code == 200:
            max_age = 60  # 1 minute default for API
            response['Cache-Control'] = f'public, max-age={max_age}'
        
        return response


class RequestCacheMiddleware:
    """
    Per-request in-memory cache.
    Store data in request._request_cache to avoid duplicate DB queries within same request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        request._request_cache = {}
        return self.get_response(request)


# Convenience export
__all__ = ['PageCacheMiddleware', 'CacheControlMiddleware', 'RequestCacheMiddleware']


# Add to settings MIDDLEWARE:
# MIDDLEWARE = [
#     ...
#     'api.cache.middleware.RequestCacheMiddleware',
#     'api.cache.middleware.PageCacheMiddleware',
#     'api.cache.middleware.CacheControlMiddleware',
# ]

import functools
import hashlib
import json
from typing import Callable, Any, Optional, Dict, Union
from datetime import datetime, timedelta
import inspect
import logging
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View

logger = logging.getLogger(__name__)

class cache_view:
    """
    Decorator for caching Django views
    Supports function-based and class-based views
    """
    
    def __init__(
        self,
        timeout: int = 300,
        key_prefix: str = "",
        vary_on_headers: list = None,
        vary_on_cookie: bool = False,
        vary_on_session: bool = False,
        vary_on_user: bool = False,
        cache_anonymous_only: bool = False,
        cache_methods: list = None,
        cache_condition: Callable = None,
        cache_backend: str = "default"
    ):
        """
        Args:
            timeout: Cache timeout in seconds
            key_prefix: Prefix for cache key
            vary_on_headers: List of headers to vary cache on
            vary_on_cookie: Whether to vary on cookies
            vary_on_session: Whether to vary on session
            vary_on_user: Whether to vary on user
            cache_anonymous_only: Cache only for anonymous users
            cache_methods: List of HTTP methods to cache (default: ['GET'])
            cache_condition: Callable that returns bool to determine if should cache
            cache_backend: Cache backend to use
        """
        self.timeout = timeout
        self.key_prefix = key_prefix
        self.vary_on_headers = vary_on_headers or []
        self.vary_on_cookie = vary_on_cookie
        self.vary_on_session = vary_on_session
        self.vary_on_user = vary_on_user
        self.cache_anonymous_only = cache_anonymous_only
        self.cache_methods = cache_methods or ['GET']
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
            cache_key = self._generate_cache_key(request, *args, **kwargs)
            
            # Try to get from cache
            cached_response = self._get_cached_response(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for view: {view_func.__name__}")
                return cached_response
            
            # Cache miss - execute view
            logger.debug(f"Cache miss for view: {view_func.__name__}")
            response = view_func(request, *args, **kwargs)
            
            # Cache the response if successful
            if self._should_cache_response(response):
                self._cache_response(cache_key, response)
            
            return response
        
        return _wrapped_view
    
    def _should_cache(self, request: HttpRequest) -> bool:
        """Determine if request should be cached"""
        # Check HTTP method
        if request.method not in self.cache_methods:
            return False
        
        # Check cache condition
        if self.cache_condition and not self.cache_condition(request):
            return False
        
        # Check anonymous only
        if self.cache_anonymous_only and request.user.is_authenticated:
            return False
        
        # Don't cache if request has cache-control: no-cache
        if 'no-cache' in request.META.get('HTTP_CACHE_CONTROL', ''):
            return False
        
        return True
    
    def _should_cache_response(self, response: HttpResponse) -> bool:
        """Determine if response should be cached"""
        # Only cache successful responses
        if response.status_code < 200 or response.status_code >= 300:
            return False
        
        # Don't cache streaming responses
        if hasattr(response, 'streaming') and response.streaming:
            return False
        
        # Check response cache-control headers
        if 'no-store' in response.get('Cache-Control', ''):
            return False
        
        return True
    
    def _generate_cache_key(self, request: HttpRequest, *args, **kwargs) -> str:
        """Generate cache key from request and arguments"""
        key_parts = [self.key_prefix or "view"]
        
        # Add view identifier
        if hasattr(request, 'resolver_match'):
            view_name = request.resolver_match.view_name
            key_parts.append(view_name)
        else:
            # Fallback to path
            key_parts.append(request.path)
        
        # Add HTTP method
        key_parts.append(request.method)
        
        # Add query parameters
        if request.GET:
            sorted_params = sorted(request.GET.items())
            param_hash = hashlib.md5(str(sorted_params).encode()).hexdigest()[:8]
            key_parts.append(f"params:{param_hash}")
        
        # Add POST data for non-GET methods (careful with sensitive data!)
        if request.method not in ['GET', 'HEAD'] and request.POST:
            # Only include non-sensitive fields
            safe_fields = ['csrfmiddlewaretoken']
            post_data = {k: v for k, v in request.POST.items() if k not in safe_fields}
            if post_data:
                post_hash = hashlib.md5(str(sorted(post_data.items())).encode()).hexdigest()[:8]
                key_parts.append(f"post:{post_hash}")
        
        # Vary on headers
        for header in self.vary_on_headers:
            header_value = request.META.get(f'HTTP_{header.upper().replace("-", "_")}')
            if header_value:
                key_parts.append(f"{header}:{header_value[:20]}")
        
        # Vary on cookie
        if self.vary_on_cookie and request.COOKIES:
            cookie_hash = hashlib.md5(str(sorted(request.COOKIES.items())).encode()).hexdigest()[:8]
            key_parts.append(f"cookie:{cookie_hash}")
        
        # Vary on session
        if self.vary_on_session and hasattr(request, 'session'):
            session_key = request.session.session_key
            if session_key:
                key_parts.append(f"session:{session_key[:8]}")
        
        # Vary on user
        if self.vary_on_user and hasattr(request, 'user'):
            if request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")
            else:
                key_parts.append("user:anonymous")
        
        # Add args and kwargs
        if args:
            key_parts.append(f"args:{hashlib.md5(str(args).encode()).hexdigest()[:8]}")
        
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(f"kwargs:{hashlib.md5(str(sorted_kwargs).encode()).hexdigest()[:8]}")
        
        # Join all parts
        return ":".join(str(part) for part in key_parts)
    
    def _get_cached_response(self, cache_key: str) -> Optional[HttpResponse]:
        """Get cached response from cache service"""
        try:
            cached_data = self.cache_service.get(cache_key)
            if cached_data:
                return self._deserialize_response(cached_data)
        except Exception as e:
            logger.error(f"Error getting cached response: {str(e)}")
        
        return None
    
    def _cache_response(self, cache_key: str, response: HttpResponse):
        """Cache response in cache service"""
        try:
            serialized = self._serialize_response(response)
            self.cache_service.set(cache_key, serialized, self.timeout)
        except Exception as e:
            logger.error(f"Error caching response: {str(e)}")
    
    def _serialize_response(self, response: HttpResponse) -> Dict[str, Any]:
        """Serialize HTTP response for caching"""
        # Get response content
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = b""
        
        # Get headers (excluding hop-by-hop headers)
        headers = {}
        for key, value in response.items():
            if key.lower() not in ['connection', 'keep-alive', 'proxy-authenticate',
                                  'proxy-authorization', 'te', 'trailers', 
                                  'transfer-encoding', 'upgrade']:
                headers[key] = value
        
        # Serialize
        return {
            'status_code': response.status_code,
            'content': content.decode('utf-8') if isinstance(content, bytes) else content,
            'headers': headers,
            'charset': getattr(response, 'charset', 'utf-8'),
            'reason_phrase': getattr(response, 'reason_phrase', 'OK'),
            'cached_at': datetime.utcnow().isoformat()
        }
    
    def _deserialize_response(self, data: Dict[str, Any]) -> HttpResponse:
        """Deserialize HTTP response from cache"""
        # Create response object
        if 'content' in data:
            content = data['content']
            if isinstance(content, str):
                content = content.encode(data.get('charset', 'utf-8'))
            response = HttpResponse(content)
        else:
            response = HttpResponse()
        
        # Set status code
        response.status_code = data.get('status_code', 200)
        
        # Set headers
        for key, value in data.get('headers', {}).items():
            response[key] = value
        
        # Add cache hit header
        response['X-Cache'] = 'HIT'
        response['X-Cache-Timestamp'] = data.get('cached_at', '')
        
        return response

# Class-based view decorator
def cache_method(
    timeout: int = 300,
    key_prefix: str = "",
    vary_on: list = None,
    **kwargs
):
    """
    Decorator for caching class-based view methods
    """
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, request, *args, **kwargs):
            # Create cache instance
            cache_decorator = cache_view(
                timeout=timeout,
                key_prefix=key_prefix or f"{self.__class__.__name__}:{method.__name__}",
                vary_on_headers=vary_on,
                **kwargs
            )
            
            # Create wrapped function
            @functools.wraps(method)
            def view_func(req, *a, **kw):
                return method(self, req, *a, **kw)
            
            # Apply cache decorator
            cached_view = cache_decorator(view_func)
            return cached_view(request, *args, **kwargs)
        
        return wrapper
    return decorator

# REST Framework support
try:
    from rest_framework.response import Response
    from rest_framework.views import APIView
    
    class cache_api_view(cache_view):
        """
        Cache decorator for Django REST Framework API views
        """
        
        def _serialize_response(self, response: Response) -> Dict[str, Any]:
            """Serialize DRF Response for caching"""
            return {
                'status_code': response.status_code,
                'data': response.data,
                'headers': dict(response.headers),
                'cached_at': datetime.utcnow().isoformat()
            }
        
        def _deserialize_response(self, data: Dict[str, Any]) -> Response:
            """Deserialize DRF Response from cache"""
            response = Response(
                data=data.get('data'),
                status=data.get('status_code', 200)
            )
            
            # Set headers
            for key, value in data.get('headers', {}).items():
                response[key] = value
            
            # Add cache headers
            response['X-Cache'] = 'HIT'
            response['X-Cache-Timestamp'] = data.get('cached_at', '')
            
            return response
    
    def cache_api_method(
        timeout: int = 300,
        key_prefix: str = "",
        vary_on: list = None,
        **kwargs
    ):
        """Decorator for caching APIView methods"""
        def decorator(method):
            @functools.wraps(method)
            def wrapper(self, request, *args, **kwargs):
                cache_decorator = cache_api_view(
                    timeout=timeout,
                    key_prefix=key_prefix or f"{self.__class__.__name__}:{method.__name__}",
                    vary_on_headers=vary_on,
                    **kwargs
                )
                
                @functools.wraps(method)
                def view_func(req, *a, **kw):
                    return method(self, req, *a, **kw)
                
                cached_view = cache_decorator(view_func)
                return cached_view(request, *args, **kwargs)
            
            return wrapper
        return decorator

except ImportError:
    # DRF not installed
    pass

# Flask support
try:
    from flask import request as flask_request, make_response
    
    class cache_flask_view:
        """
        Cache decorator for Flask views
        """
        
        def __init__(
            self,
            timeout: int = 300,
            key_prefix: str = "",
            vary_on_headers: list = None,
            vary_on_cookie: bool = False,
            vary_on_session: bool = False,
            vary_on_user: bool = False,
            cache_methods: list = None,
            **kwargs
        ):
            self.timeout = timeout
            self.key_prefix = key_prefix
            self.vary_on_headers = vary_on_headers or []
            self.vary_on_cookie = vary_on_cookie
            self.vary_on_session = vary_on_session
            self.vary_on_user = vary_on_user
            self.cache_methods = cache_methods or ['GET']
            
            from api.cache.manager import cache_manager
            self.cache_service = cache_manager.get_cache(kwargs.get('cache_backend', 'default'))
        
        def __call__(self, view_func):
            @functools.wraps(view_func)
            def wrapper(*args, **kwargs):
                # Check if should cache
                if not self._should_cache():
                    return view_func(*args, **kwargs)
                
                # Generate cache key
                cache_key = self._generate_cache_key(*args, **kwargs)
                
                # Try to get from cache
                cached = self.cache_service.get(cache_key)
                if cached:
                    response = make_response(cached['content'])
                    response.status_code = cached['status_code']
                    for key, value in cached['headers'].items():
                        response.headers[key] = value
                    response.headers['X-Cache'] = 'HIT'
                    return response
                
                # Cache miss
                response = view_func(*args, **kwargs)
                
                # Cache the response
                if response.status_code == 200:
                    cache_data = {
                        'content': response.get_data(as_text=True),
                        'status_code': response.status_code,
                        'headers': dict(response.headers)
                    }
                    self.cache_service.set(cache_key, cache_data, self.timeout)
                
                response.headers['X-Cache'] = 'MISS'
                return response
            
            return wrapper
        
        def _should_cache(self):
            return flask_request.method in self.cache_methods
        
        def _generate_cache_key(self, *args, **kwargs):
            key_parts = [self.key_prefix or "flask", flask_request.endpoint]
            
            # Add path and query
            key_parts.append(flask_request.path)
            if flask_request.args:
                sorted_args = sorted(flask_request.args.items())
                args_hash = hashlib.md5(str(sorted_args).encode()).hexdigest()[:8]
                key_parts.append(f"args:{args_hash}")
            
            return ":".join(key_parts)

except ImportError:
    # Flask not installed
    pass
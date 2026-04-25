"""
api/ad_networks/decorators.py
Custom decorators for ad networks module
SaaS-ready with tenant support
"""

import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Any, Optional

from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def tenant_required(view_func: Callable) -> Callable:
    """
    Decorator to require tenant context
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get tenant ID from request
        tenant_id = getattr(request, 'tenant_id', None)
        
        if not tenant_id:
            # Try to get from subdomain or header
            tenant_id = get_tenant_from_request(request)
        
        if not tenant_id:
            return JsonResponse({
                'error': 'Tenant context required',
                'code': 'tenant_required'
            }, status=400)
        
        # Add tenant to request
        request.tenant_id = tenant_id
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_isolation(view_func: Callable) -> Callable:
    """
    Decorator to enforce tenant isolation
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant_id = getattr(request, 'tenant_id', None)
        
        if not tenant_id:
            return JsonResponse({
                'error': 'Tenant context required',
                'code': 'tenant_required'
            }, status=400)
        
        # Validate tenant exists and is active
        if not validate_tenant(tenant_id):
            return JsonResponse({
                'error': 'Invalid or inactive tenant',
                'code': 'tenant_invalid'
            }, status=403)
        
        # Add tenant to request
        request.tenant_id = tenant_id
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def rate_limit(max_requests: int = 100, window_minutes: int = 60, 
                scope: str = 'ip', key_func: Callable = None):
    """
    Decorator to implement rate limiting
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get cache key
            if key_func:
                cache_key = key_func(request)
            elif scope == 'ip':
                cache_key = f"rate_limit_{get_client_ip(request)}"
            elif scope == 'user':
                user_id = getattr(request.user, 'id', None)
                if user_id:
                    cache_key = f"rate_limit_user_{user_id}"
                else:
                    cache_key = f"rate_limit_ip_{get_client_ip(request)}"
            else:
                cache_key = f"rate_limit_global"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Check if rate limit exceeded
            if current_count >= max_requests:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'code': 'rate_limit_exceeded',
                    'retry_after': window_minutes * 60
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, current_count + 1, window_minutes * 60)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_subscription(plan_level: str = 'basic'):
    """
    Decorator to require subscription plan
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            
            if not user or not user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required',
                    'code': 'auth_required'
                }, status=401)
            
            # Check user subscription
            if not has_subscription(user, plan_level):
                return JsonResponse({
                    'error': f'{plan_level.title()} subscription required',
                    'code': 'subscription_required'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_verification(view_func: Callable) -> Callable:
    """
    Decorator to require user verification
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        
        if not user or not user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'auth_required'
            }, status=401)
        
        # Check if user is verified
        if not is_user_verified(user):
            return JsonResponse({
                'error': 'User verification required',
                'code': 'verification_required'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def log_api_call(view_func: Callable) -> Callable:
    """
    Decorator to log API calls
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        
        try:
            response = view_func(request, *args, **kwargs)
            
            # Log successful call
            log_api_call_data(request, response, start_time, success=True)
            
            return response
            
        except Exception as e:
            # Log failed call
            log_api_call_data(request, None, start_time, success=False, error=str(e))
            raise
    
    return wrapper


def cache_response(timeout: int = 300, key_func: Callable = None):
    """
    Decorator to cache response
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(request, *args, **kwargs)
            else:
                cache_key = f"cache_{request.path}_{request.GET.urlencode()}"
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response
            
            # Execute view
            response = view_func(request, *args, **kwargs)
            
            # Cache response if it's successful
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        
        return wrapper
    return decorator


def validate_ip_whitelist(view_func: Callable) -> Callable:
    """
    Decorator to validate IP whitelist
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        client_ip = get_client_ip(request)
        
        # Check if IP is whitelisted
        if not is_ip_whitelisted(client_ip):
            return JsonResponse({
                'error': 'IP address not allowed',
                'code': 'ip_not_allowed'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_geo_access(allowed_countries: list = None):
    """
    Decorator to require geographic access
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get user country
            user_country = get_user_country(request)
            
            if user_country and allowed_countries and user_country not in allowed_countries:
                return JsonResponse({
                    'error': f'Access not allowed from {user_country}',
                    'code': 'geo_restricted'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def track_analytics(event_type: str):
    """
    Decorator to track analytics events
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Track page view
            track_analytics_event(event_type, {
                'path': request.path,
                'method': request.method,
                'user_id': getattr(request.user, 'id', None),
                'tenant_id': getattr(request, 'tenant_id', None),
                'timestamp': timezone.now().isoformat()
            })
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Track response
                track_analytics_event(f"{event_type}_response", {
                    'path': request.path,
                    'status_code': getattr(response, 'status_code', None),
                    'user_id': getattr(request.user, 'id', None),
                    'tenant_id': getattr(request, 'tenant_id', None),
                    'timestamp': timezone.now().isoformat()
                })
                
                return response
                
            except Exception as e:
                # Track error
                track_analytics_event(f"{event_type}_error", {
                    'path': request.path,
                    'error': str(e),
                    'user_id': getattr(request.user, 'id', None),
                    'tenant_id': getattr(request, 'tenant_id', None),
                    'timestamp': timezone.now().isoformat()
                })
                raise
        
        return wrapper
    return decorator


def handle_api_errors(view_func: Callable) -> Callable:
    """
    Decorator to handle API errors consistently
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"API error in {view_func.__name__}: {str(e)}")
            
            return JsonResponse({
                'error': 'Internal server error',
                'code': 'internal_error',
                'details': str(e) if settings.DEBUG else None
            }, status=500)
    
    return wrapper


def require_feature_flag(feature_flag: str):
    """
    Decorator to require feature flag
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if feature flag is enabled
            if not is_feature_enabled(feature_flag):
                return JsonResponse({
                    'error': 'Feature not available',
                    'code': 'feature_disabled'
                }, status=503)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def throttle_requests(max_requests: int = 10, period_seconds: int = 60):
    """
    Decorator to throttle requests
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            client_ip = get_client_ip(request)
            cache_key = f"throttle_{client_ip}_{view_func.__name__}"
            
            # Get current request count
            request_count = cache.get(cache_key, 0)
            
            # Check if throttled
            if request_count >= max_requests:
                return JsonResponse({
                    'error': 'Too many requests',
                    'code': 'throttled',
                    'retry_after': period_seconds
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, request_count + 1, period_seconds)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Helper functions
def get_tenant_from_request(request) -> Optional[str]:
    """
    Get tenant ID from request
    """
    # Try subdomain
    host = request.get_host()
    if host:
        subdomain = host.split('.')[0]
        if subdomain and subdomain != 'www':
            return subdomain
    
    # Try header
    tenant_id = request.META.get('HTTP_X_TENANT_ID')
    if tenant_id:
        return tenant_id
    
    # Try query parameter
    tenant_id = request.GET.get('tenant_id')
    if tenant_id:
        return tenant_id
    
    return None


def get_client_ip(request) -> str:
    """
    Get client IP address
    """
    # Try X-Forwarded-For header
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    # Try X-Real-IP header
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    # Try REMOTE_ADDR
    return request.META.get('REMOTE_ADDR')


def validate_tenant(tenant_id: str) -> bool:
    """
    Validate tenant exists and is active
    """
    try:
        # This would check your tenant model
        # For now, return True for demo
        return True
    except Exception as e:
        logger.error(f"Error validating tenant {tenant_id}: {str(e)}")
        return False


def has_subscription(user, plan_level: str) -> bool:
    """
    Check if user has required subscription
    """
    try:
        # This would check your subscription model
        # For now, return True for demo
        return True
    except Exception as e:
        logger.error(f"Error checking subscription for user {user.id}: {str(e)}")
        return False


def is_user_verified(user) -> bool:
    """
    Check if user is verified
    """
    try:
        # This would check your user verification model
        # For now, return True for demo
        return True
    except Exception as e:
        logger.error(f"Error checking verification for user {user.id}: {str(e)}")
        return False


def is_ip_whitelisted(ip_address: str) -> bool:
    """
    Check if IP is whitelisted
    """
    try:
        # This would check your IP whitelist model
        # For now, return True for demo
        return True
    except Exception as e:
        logger.error(f"Error checking IP whitelist for {ip_address}: {str(e)}")
        return False


def get_user_country(request) -> Optional[str]:
    """
    Get user country from request
    """
    # Try GeoIP lookup
    ip_address = get_client_ip(request)
    
    # This would integrate with GeoIP service
    # For now, return US for demo
    return 'US'


def log_api_call_data(request, response, start_time: float, success: bool = True, error: str = None):
    """
    Log API call data
    """
    try:
        duration = time.time() - start_time
        
        log_data = {
            'path': request.path,
            'method': request.method,
            'user_id': getattr(request.user, 'id', None),
            'tenant_id': getattr(request, 'tenant_id', None),
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'timestamp': timezone.now().isoformat(),
            'duration_ms': duration * 1000,
            'success': success,
            'status_code': getattr(response, 'status_code', None) if response else None,
            'error': error
        }
        
        # This would save to your API log model
        logger.info(f"API call: {log_data}")
        
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}")


def track_analytics_event(event_type: str, data: dict):
    """
    Track analytics event
    """
    try:
        # This would integrate with your analytics service
        logger.info(f"Analytics event {event_type}: {data}")
    except Exception as e:
        logger.error(f"Error tracking analytics event {event_type}: {str(e)}")


def is_feature_enabled(feature_flag: str) -> bool:
    """
    Check if feature flag is enabled
    """
    try:
        # This would check your feature flag service
        # For now, return True for demo
        return True
    except Exception as e:
        logger.error(f"Error checking feature flag {feature_flag}: {str(e)}")
        return False


# Class-based decorators
class MethodDecorator:
    """
    Base class for method decorators
    """
    
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.before_call(func, *args, **kwargs)
        return wrapper
    
    def before_call(self, func, *args, **kwargs):
        """Override this method in subclasses"""
        return func(*args, **kwargs)


class TimingDecorator(MethodDecorator):
    """
    Decorator to time method execution
    """
    
    def before_call(self, func, *args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(f"Method {func.__name__} executed in {duration:.3f}s")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Method {func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise


class RetryDecorator(MethodDecorator):
    """
    Decorator to retry method on failure
    """
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
        super().__init__(max_retries, delay, exceptions)
        self.max_retries = max_retries
        self.delay = delay
        self.exceptions = exceptions
    
    def before_call(self, func, *args, **kwargs):
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.exceptions as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    logger.warning(f"Method {func.__name__} failed (attempt {attempt + 1}), retrying in {self.delay}s: {str(e)}")
                    time.sleep(self.delay)
                else:
                    logger.error(f"Method {func.__name__} failed after {self.max_retries} attempts: {str(e)}")
                    raise
        
        raise last_exception


class CacheDecorator(MethodDecorator):
    """
    Decorator to cache method results
    """
    
    def __init__(self, timeout: int = 300, key_func=None):
        super().__init__(timeout, key_func)
        self.timeout = timeout
        self.key_func = key_func
    
    def before_call(self, func, *args, **kwargs):
        # Generate cache key
        if self.key_func:
            cache_key = self.key_func(*args, **kwargs)
        else:
            cache_key = f"cache_{func.__name__}_{hash(str(args) + str(kwargs))}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Execute function and cache result
        result = func(*args, **kwargs)
        cache.set(cache_key, result, self.timeout)
        
        return result


# Usage examples:
# @tenant_required
# @rate_limit(max_requests=100, window_minutes=60)
# @require_subscription('premium')
# @require_verification
# @log_api_call
# @cache_response(timeout=300)
# @validate_ip_whitelist
# @require_geo_access(['US', 'GB', 'CA'])
# @track_analytics('page_view')
# @handle_api_errors
# @require_feature_flag('new_feature')
# @throttle_requests(max_requests=10, period_seconds=60)

# Class-based decorators:
# @TimingDecorator()
# @RetryDecorator(max_retries=3, delay=1.0)
# @CacheDecorator(timeout=300)

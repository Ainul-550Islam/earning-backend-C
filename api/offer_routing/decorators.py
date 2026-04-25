"""
Decorators for Offer Routing System

This module contains custom decorators for the offer routing system,
including caching, rate limiting, authentication, and performance monitoring.
"""

import logging
import time
import functools
from typing import Any, Callable, Dict, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def cache_result(timeout: int = 300, key_prefix: str = "", vary_on: list = None):
    """
    Decorator to cache the result of a function.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
        vary_on: List of arguments to include in cache key
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key_parts = [key_prefix, func.__name__]
            
            if vary_on:
                for arg_name in vary_on:
                    if arg_name in kwargs:
                        cache_key_parts.append(f"{arg_name}:{kwargs[arg_name]}")
                    elif len(args) > 0:
                        # Try to get from args by position
                        try:
                            # This is a simplified approach
                            cache_key_parts.append(f"{arg_name}:{args[0]}")
                        except IndexError:
                            pass
            
            cache_key = ":".join(str(part) for part in cache_key_parts)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for key: {cache_key}")
            
            return result
        return wrapper
    return decorator


def rate_limit(requests_per_minute: int = 60, key_func: Callable = None):
    """
    Decorator to implement rate limiting.
    
    Args:
        requests_per_minute: Number of requests allowed per minute
        key_func: Function to generate rate limit key (defaults to IP address)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get request object
            request = None
            for arg in args:
                if hasattr(arg, 'META'):
                    request = arg
                    break
            
            if not request:
                return func(*args, **kwargs)
            
            # Generate rate limit key
            if key_func:
                rate_key = key_func(request)
            else:
                rate_key = f"rate_limit:{request.META.get('REMOTE_ADDR', 'unknown')}"
            
            # Get current count
            current_count = cache.get(rate_key, 0)
            
            if current_count >= requests_per_minute:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {requests_per_minute} requests per minute allowed'
                }, status=429)
            
            # Increment counter
            cache.set(rate_key, current_count + 1, 60)  # 60 seconds = 1 minute
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_permissions(permissions: list):
    """
    Decorator to check if user has required permissions.
    
    Args:
        permissions: List of permission strings required
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required'
                }, status=401)
            
            # Check permissions
            user_permissions = request.user.get_all_permissions()
            for permission in permissions:
                if permission not in user_permissions:
                    return JsonResponse({
                        'error': 'Permission denied',
                        'required_permissions': permissions
                    }, status=403)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def log_execution_time(log_level: str = 'INFO'):
    """
    Decorator to log function execution time.
    
    Args:
        log_level: Logging level for the execution time
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.log(
                    getattr(logging, log_level.upper()),
                    f"Function {func.__name__} executed in {execution_time:.4f} seconds"
                )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.error(
                    f"Function {func.__name__} failed after {execution_time:.4f} seconds: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def validate_input(validator: Callable):
    """
    Decorator to validate input parameters.
    
    Args:
        validator: Function to validate input parameters
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                validator(*args, **kwargs)
            except ValueError as e:
                return JsonResponse({
                    'error': 'Validation failed',
                    'message': str(e)
                }, status=400)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def handle_exceptions(default_response: Any = None, log_error: bool = True):
    """
    Decorator to handle exceptions gracefully.
    
    Args:
        default_response: Default response to return on exception
        log_error: Whether to log the error
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Exception in {func.__name__}: {str(e)}", exc_info=True)
                
                if default_response is not None:
                    return default_response
                
                return JsonResponse({
                    'error': 'Internal server error',
                    'message': 'An unexpected error occurred'
                }, status=500)
        return wrapper
    return decorator


def require_feature_flag(feature_name: str):
    """
    Decorator to check if a feature flag is enabled.
    
    Args:
        feature_name: Name of the feature flag to check
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check feature flag
            feature_flags = getattr(settings, 'FEATURE_FLAGS', {})
            
            if not feature_flags.get(feature_name, False):
                return JsonResponse({
                    'error': 'Feature not available',
                    'feature': feature_name
                }, status=503)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def conditional_cache(condition_func: Callable, timeout: int = 300):
    """
    Decorator to conditionally cache results based on a condition function.
    
    Args:
        condition_func: Function that determines if result should be cached
        timeout: Cache timeout in seconds
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Check if we should cache this result
            if condition_func(*args, **kwargs):
                cache_key = f"conditional_cache:{func.__name__}:{hash(str(args) + str(kwargs))}"
                cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function on failure.
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {current_delay}s: {str(e)}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


def track_performance(metric_name: str = None):
    """
    Decorator to track performance metrics.
    
    Args:
        metric_name: Name of the metric (defaults to function name)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metric_name_to_use = metric_name or f"{func.__module__}.{func.__name__}"
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Store performance metric
                cache_key = f"performance:{metric_name_to_use}"
                cache.set(cache_key, execution_time, timeout=3600)  # Store for 1 hour
                
                # Log performance
                logger.info(f"Performance: {metric_name_to_use} took {execution_time:.4f}s")
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                # Store error metric
                error_key = f"performance_error:{metric_name_to_use}"
                cache.set(error_key, execution_time, timeout=3600)
                
                logger.error(f"Performance error: {metric_name_to_use} failed after {execution_time:.4f}s: {str(e)}")
                raise
        
        return wrapper
    return decorator


def api_auth_required():
    """
    Decorator for API authentication requirement.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Check for API key in headers
            api_key = request.META.get('HTTP_X_API_KEY')
            
            if not api_key:
                return JsonResponse({
                    'error': 'API key required'
                }, status=401)
            
            # Validate API key (implement your validation logic)
            valid_api_keys = getattr(settings, 'VALID_API_KEYS', [])
            if api_key not in valid_api_keys:
                return JsonResponse({
                    'error': 'Invalid API key'
                }, status=401)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def tenant_required():
    """
    Decorator to require tenant context.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Check for tenant in request
            tenant_id = getattr(request, 'tenant_id', None)
            
            if not tenant_id:
                return JsonResponse({
                    'error': 'Tenant context required'
                }, status=400)
            
            # Validate tenant (implement your validation logic)
            from .models import TenantSettings
            try:
                tenant = TenantSettings.objects.get(user_id=tenant_id)
                request.tenant = tenant
            except TenantSettings.DoesNotExist:
                return JsonResponse({
                    'error': 'Invalid tenant'
                }, status=404)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# DRF-specific decorators
def drf_cache_result(timeout: int = 300, key_prefix: str = ""):
    """
    Decorator for DRF views to cache results.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(view, request, *args, **kwargs):
            # Generate cache key
            cache_key = f"drf_cache:{key_prefix}:{view.__class__.__name__}:{request.get_full_path()}"
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response)
            
            # Execute view and cache result
            response = view_func(view, request, *args, **kwargs)
            
            if response.status_code == 200:
                cache.set(cache_key, response.data, timeout)
            
            return response
        return wrapper
    return decorator


def drf_rate_limit(requests_per_minute: int = 60):
    """
    Rate limiting decorator for DRF views.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(view, request, *args, **kwargs):
            # Get client IP
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            rate_key = f"drf_rate_limit:{client_ip}"
            
            # Check rate limit
            current_count = cache.get(rate_key, 0)
            
            if current_count >= requests_per_minute:
                return Response({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {requests_per_minute} requests per minute allowed'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Increment counter
            cache.set(rate_key, current_count + 1, 60)
            
            return view_func(view, request, *args, **kwargs)
        return wrapper
    return decorator


# Combined decorators for common use cases
def secure_api_view(methods: list = None, cache_timeout: int = 300, rate_limit_per_minute: int = 60):
    """
    Combined decorator for secure API views.
    
    Args:
        methods: Allowed HTTP methods
        cache_timeout: Cache timeout in seconds
        rate_limit_per_minute: Rate limit per minute
    """
    def decorator(func):
        # Apply decorators in order
        decorated_func = func
        
        if methods:
            decorated_func = require_http_methods(methods)(decorated_func)
        
        decorated_func = api_auth_required()(decorated_func)
        decorated_func = rate_limit(rate_limit_per_minute)(decorated_func)
        decorated_func = cache_result(timeout=cache_timeout)(decorated_func)
        decorated_func = handle_exceptions()(decorated_func)
        
        return decorated_func
    return decorator


def secure_drf_view(cache_timeout: int = 300, rate_limit_per_minute: int = 60):
    """
    Combined decorator for secure DRF views.
    
    Args:
        cache_timeout: Cache timeout in seconds
        rate_limit_per_minute: Rate limit per minute
    """
    def decorator(view_func):
        # Apply decorators in order
        decorated_func = view_func
        
        decorated_func = permission_classes([IsAuthenticated])(decorated_func)
        decorated_func = drf_rate_limit(rate_limit_per_minute)(decorated_func)
        decorated_func = drf_cache_result(timeout=cache_timeout)(decorated_func)
        
        return decorated_func
    return decorator


# Export all decorators
__all__ = [
    'cache_result',
    'rate_limit',
    'require_permissions',
    'log_execution_time',
    'validate_input',
    'handle_exceptions',
    'require_feature_flag',
    'conditional_cache',
    'retry_on_failure',
    'track_performance',
    'api_auth_required',
    'tenant_required',
    'drf_cache_result',
    'drf_rate_limit',
    'secure_api_view',
    'secure_drf_view',
]

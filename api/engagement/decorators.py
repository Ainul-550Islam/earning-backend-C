# engagement/decorators.py
"""
Custom decorators for engagement system.
Includes caching, rate limiting, permissions, and utility decorators.
"""
import functools
import time
from datetime import datetime, timedelta
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .dependencies import is_feature_enabled
from .exceptions import EngagementError, RateLimitExceededError


def engagement_endpoint(view_func):
    """
    Decorator for engagement API endpoints.
    Provides consistent error handling and response format.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            result = view_func(request, *args, **kwargs)
            return result
        except EngagementError as exc:
            return Response({
                'success': False,
                'error': exc.detail,
                'code': exc.default_code,
                'type': exc.__class__.__name__
            }, status=exc.status_code)
        except Exception as exc:
            return Response({
                'success': False,
                'error': 'Internal server error',
                'type': 'InternalServerError'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return wrapper


def rate_limit(key_prefix, limit=100, period=3600, scope='ip'):
    """
    Rate limiting decorator.
    
    Args:
        key_prefix: Prefix for cache key
        limit: Number of allowed requests
        period: Time period in seconds
        scope: 'ip', 'user', or custom function
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if scope == 'ip':
                identifier = request.META.get('REMOTE_ADDR', 'unknown')
            elif scope == 'user' and request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            elif callable(scope):
                identifier = scope(request)
            else:
                identifier = 'anonymous'
            
            cache_key = f"rate_limit:{key_prefix}:{identifier}"
            
            # Check current count
            current_count = cache.get(cache_key, 0)
            
            if current_count >= limit:
                raise RateLimitExceededError(
                    f"Rate limit exceeded. {limit} requests per {period} seconds."
                )
            
            # Increment counter
            cache.set(cache_key, current_count + 1, period)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def cache_result(key_prefix, timeout=300, vary_on=None):
    """
    Cache decorator for view results.
    
    Args:
        key_prefix: Prefix for cache key
        timeout: Cache timeout in seconds
        vary_on: List of request attributes to vary cache on
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix]
            
            if vary_on:
                for attr in vary_on:
                    if hasattr(request, attr):
                        value = getattr(request, attr)
                        if callable(value):
                            value = value()
                        key_parts.append(str(value))
            
            cache_key = f"view_cache:{':'.join(key_parts)}"
            
            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute view and cache result
            result = view_func(request, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def require_tenant(view_func):
    """
    Decorator to require tenant context.
    Ensures request has tenant information available.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            return Response({
                'success': False,
                'error': 'Tenant context required',
                'code': 'tenant_required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def feature_flag(feature_name, fallback_response=None):
    """
    Decorator to check if a feature is enabled.
    
    Args:
        feature_name: Name of the feature to check
        fallback_response: Response to return if feature is disabled
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not is_feature_enabled(feature_name):
                if fallback_response:
                    return fallback_response
                return Response({
                    'success': False,
                    'error': f'Feature {feature_name} is not available',
                    'code': 'feature_disabled'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def validate_request(serializer_class):
    """
    Decorator to validate request data using DRF serializer.
    
    Args:
        serializer_class: Serializer class to use for validation
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                serializer = serializer_class(data=request.data)
                if not serializer.is_valid():
                    return Response({
                        'success': False,
                        'error': 'Validation failed',
                        'details': serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Add validated data to request
                request.validated_data = serializer.validated_data
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def log_engagement_action(action_type):
    """
    Decorator to automatically log engagement actions.
    
    Args:
        action_type: Type of action to log
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = view_func(request, *args, **kwargs)
                success = True
            except Exception as exc:
                success = False
                raise
            finally:
                # Log the action
                duration = time.time() - start_time
                
                try:
                    from .services.analytics_service import AnalyticsService
                    
                    AnalyticsService.record(
                        request.user if request.user.is_authenticated else None,
                        f"{action_type}_api_call",
                        properties={
                            'endpoint': request.path,
                            'method': request.method,
                            'success': success,
                            'duration': duration,
                            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        },
                        tenant=getattr(request.user, 'tenant', None) if request.user.is_authenticated else None
                    )
                except Exception:
                    # Silently ignore logging errors
                    pass
            
            return result
        return wrapper
    return decorator


def require_active_user(view_func):
    """
    Decorator to require user to be active.
    Checks user status and prevents suspended/banned users.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({
                'success': False,
                'error': 'Authentication required',
                'code': 'authentication_required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check user status
        user_status = getattr(request.user, 'status', 'active')
        if user_status != 'active':
            return Response({
                'success': False,
                'error': 'Account is not active',
                'code': 'account_inactive'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def maintenance_mode(view_func):
    """
    Decorator to handle maintenance mode.
    Returns maintenance response if system is under maintenance.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check maintenance mode flag
        maintenance_flag = cache.get('engagement_maintenance_mode', False)
        
        if maintenance_flag:
            return Response({
                'success': False,
                'error': 'System is under maintenance',
                'code': 'maintenance_mode',
                'message': 'We\'re currently performing maintenance. Please try again later.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def beta_feature(view_func):
    """
    Decorator for beta features.
    Adds beta warning headers and checks user beta access.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user has beta access
        if request.user.is_authenticated:
            has_beta_access = getattr(request.user, 'has_beta_access', False)
            if not has_beta_access:
                return Response({
                    'success': False,
                    'error': 'Beta access required',
                    'code': 'beta_access_required'
                }, status=status.HTTP_403_FORBIDDEN)
        
        response = view_func(request, *args, **kwargs)
        
        # Add beta warning headers
        if hasattr(response, 'headers'):
            response.headers['X-Beta-Feature'] = 'true'
            response.headers['X-Beta-Warning'] = 'This is a beta feature and may change'
        
        return response
    return wrapper


def throttle_action(action_type, limit=10, period=60):
    """
    Decorator to throttle specific actions.
    
    Args:
        action_type: Type of action being throttled
        limit: Number of allowed actions
        period: Time period in seconds
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            # Generate throttle key
            throttle_key = f"throttle:{action_type}:user_{request.user.id}"
            
            # Check current count
            current_count = cache.get(throttle_key, 0)
            
            if current_count >= limit:
                return Response({
                    'success': False,
                    'error': f'Too many {action_type} actions. Please try again later.',
                    'code': 'throttled',
                    'retry_after': period
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Increment counter
            cache.set(throttle_key, current_count + 1, period)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def class_method_decorator(decorator):
    """
    Class method decorator that preserves self/cls.
    """
    def __get__(self, obj, objtype=None):
        if obj is None:
            # Decorate class method
            return self.decorate_class_method(objtype)
        else:
            # Decorate instance method
            return self.decorate_instance_method(obj)
    
    def decorate_class_method(self, cls):
        """
        Decorate a class method.
        """
        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            return decorator(cls(*args, **kwargs))
        return wrapper
    
    def decorate_instance_method(self, instance):
        """
        Decorate an instance method.
        """
        @functools.wraps(self.func)
        def wrapper(*args, **kwargs):
            return self.func(instance, *args, **kwargs)
        return wrapper


# ── Combined Decorators ───────────────────────────────────────────────────────

def api_engagement_endpoint(methods=['GET'], auth_required=True, rate_limit=None):
    """
    Combined decorator for engagement API endpoints.
    
    Args:
        methods: Allowed HTTP methods
        auth_required: Whether authentication is required
        rate_limit: Rate limit configuration (limit, period)
    """
    def decorator(view_func):
        # Apply method restriction
        decorated = api_view(methods)(view_func)
        
        # Apply authentication requirement
        if auth_required:
            decorated = permission_classes([IsAuthenticated])(decorated)
        
        # Apply engagement endpoint wrapper
        decorated = engagement_endpoint(decorated)
        
        # Apply rate limiting
        if rate_limit:
            limit, period = rate_limit
            decorated = rate_limit('api_endpoint', limit, period, 'user')(decorated)
        
        # Apply logging
        decorated = log_engagement_action('api')(decorated)
        
        return decorated
    return decorator


def cached_engagement_view(key_prefix, timeout=300, vary_on=None):
    """
    Combined decorator for cached engagement views.
    """
    def decorator(view_func):
        decorated = cache_result(key_prefix, timeout, vary_on)(view_func)
        decorated = engagement_endpoint(decorated)
        return decorated
    return decorator


def premium_feature(feature_name):
    """
    Decorator for premium features that require subscription.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response({
                    'success': False,
                    'error': 'Authentication required',
                    'code': 'authentication_required'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Check if user has premium access
            has_premium = getattr(request.user, 'has_premium', False)
            if not has_premium:
                return Response({
                    'success': False,
                    'error': 'Premium subscription required',
                    'code': 'premium_required',
                    'upgrade_url': '/pricing'
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

"""
Tenant Decorators - Function and Method Decorators

This module contains comprehensive decorators for tenant-related functions
including security, caching, validation, and performance monitoring.
"""

import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models_improved import Tenant
from .permissions_improved import IsTenantOwner, IsTenantMember
from .services_improved import tenant_security_service
from .constants import TENANT_ERROR_MESSAGES

logger = logging.getLogger(__name__)


def tenant_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure tenant context is available.
    
    This decorator checks that a tenant is available in the request
    and raises an error if not.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'tenant') or not request.tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        if not request.tenant.is_active or request.tenant.is_deleted:
            return JsonResponse({
                'error': 'Tenant not available',
                'message': 'Tenant is not active or has been deleted'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_owner_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure user is tenant owner.
    
    This decorator checks that the current user is the owner
    of the tenant or a superuser.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'message': 'You must be logged in to perform this action'
            }, status=401)
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        # Check if user is owner or superuser
        if not (request.user.is_superuser or tenant.owner == request.user):
            return JsonResponse({
                'error': 'Access denied',
                'message': TENANT_ERROR_MESSAGES['access_denied']
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_member_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure user is tenant member.
    
    This decorator checks that the current user is a member
    of the tenant or a superuser.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'message': 'You must be logged in to perform this action'
            }, status=401)
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        # Check if user is owner, member, or superuser
        is_member = (request.user.is_superuser or 
                    tenant.owner == request.user or
                    hasattr(request.user, 'tenant') and request.user.tenant == tenant)
        
        if not is_member:
            return JsonResponse({
                'error': 'Access denied',
                'message': TENANT_ERROR_MESSAGES['access_denied']
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_active_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure tenant is active.
    
    This decorator checks that the tenant is active and not suspended.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        if not tenant.is_active or tenant.is_deleted:
            return JsonResponse({
                'error': 'Tenant not active',
                'message': 'Tenant is not active or has been deleted'
            }, status=403)
        
        if tenant.is_suspended:
            return JsonResponse({
                'error': 'Tenant suspended',
                'message': TENANT_ERROR_MESSAGES['suspended']
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_subscription_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure tenant has active subscription.
    
    This decorator checks that the tenant has an active subscription
    or is still in trial period.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        # Check subscription status
        try:
            billing = tenant.get_billing()
            if not billing.is_active and not tenant.is_trial_active:
                return JsonResponse({
                    'error': 'Subscription required',
                    'message': TENANT_ERROR_MESSAGES['subscription_inactive']
                }, status=403)
        except Exception:
            return JsonResponse({
                'error': 'Billing information unavailable',
                'message': 'Unable to verify subscription status'
            }, status=500)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_feature_required(feature_name: str):
    """
    Decorator to ensure tenant has specific feature enabled.
    
    Args:
        feature_name: Name of the required feature
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return JsonResponse({
                    'error': 'Tenant context required',
                    'message': TENANT_ERROR_MESSAGES['tenant_not_found']
                }, status=400)
            
            # Check if feature is enabled
            if not tenant.has_feature(feature_name):
                return JsonResponse({
                    'error': 'Feature not available',
                    'message': TENANT_ERROR_MESSAGES['feature_disabled']
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def tenant_rate_limit(max_requests: int = 100, window: int = 3600):
    """
    Decorator to implement rate limiting for tenant operations.
    
    Args:
        max_requests: Maximum number of requests allowed
        window: Time window in seconds
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return view_func(request, *args, **kwargs)
            
            # Get client IP
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Check rate limit
            if not tenant_security_service.check_rate_limit(
                tenant, 'decorator_limit', client_ip, max_requests
            ):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': TENANT_ERROR_MESSAGES['rate_limit_exceeded']
                }, status=429)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def tenant_cache(timeout: int = 300, key_prefix: str = 'tenant'):
    """
    Decorator to cache function results with tenant-specific keys.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return view_func(request, *args, **kwargs)
            
            # Generate cache key
            cache_key = f"{key_prefix}_{tenant.id}_{view_func.__name__}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = view_func(request, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def tenant_audit_log(action: str = 'custom_action'):
    """
    Decorator to log tenant actions for audit purposes.
    
    Args:
        action: Action name for audit log
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = view_func(request, *args, **kwargs)
                success = True
                error_message = None
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # Log the action
                tenant = getattr(request, 'tenant', None)
                if tenant:
                    execution_time = time.time() - start_time
                    
                    audit_details = {
                        'function': view_func.__name__,
                        'execution_time': execution_time,
                        'success': success,
                        'error_message': error_message,
                        'request_path': request.path,
                        'request_method': request.method,
                    }
                    
                    try:
                        tenant.audit_log(
                            action=action,
                            details=audit_details,
                            user=request.user if request.user.is_authenticated else None
                        )
                    except Exception as e:
                        logger.error(f"Failed to log audit action: {e}")
            
            return result
        
        return wrapper
    return decorator


def tenant_performance_monitor(threshold_ms: int = 1000):
    """
    Decorator to monitor function performance.
    
    Args:
        threshold_ms: Performance threshold in milliseconds
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = view_func(request, *args, **kwargs)
                
                execution_time_ms = (time.time() - start_time) * 1000
                
                if execution_time_ms > threshold_ms:
                    tenant = getattr(request, 'tenant', None)
                    logger.warning(
                        f"Slow function detected: {view_func.__name__} "
                        f"took {execution_time_ms:.2f}ms "
                        f"(threshold: {threshold_ms}ms) "
                        f"for tenant: {tenant.name if tenant else 'unknown'}"
                    )
                
                return result
                
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Function {view_func.__name__} failed after "
                    f"{execution_time_ms:.2f}ms: {e}"
                )
                raise
        
        return wrapper
    return decorator


def tenant_user_limit_check(view_func: Callable) -> Callable:
    """
    Decorator to check if tenant has reached user limit.
    
    This decorator checks if the tenant has reached their maximum
    user limit and blocks new user creation if so.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return view_func(request, *args, **kwargs)
        
        # Check user limit
        if tenant.is_user_limit_reached():
            return JsonResponse({
                'error': 'User limit reached',
                'message': TENANT_ERROR_MESSAGES['user_limit_reached']
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_maintenance_mode(view_func: Callable) -> Callable:
    """
    Decorator to check if tenant is in maintenance mode.
    
    This decorator blocks access if the tenant is in maintenance mode.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return view_func(request, *args, **kwargs)
        
        # Check maintenance mode
        try:
            settings = tenant.get_settings()
            if getattr(settings, 'maintenance_mode', False):
                return JsonResponse({
                    'error': 'Maintenance mode',
                    'message': TENANT_ERROR_MESSAGES['maintenance_mode']
                }, status=503)
        except Exception:
            pass
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_api_key_required(view_func: Callable) -> Callable:
    """
    Decorator to require valid API key for access.
    
    This decorator checks for a valid API key in the request headers.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get API key from headers
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            api_key = request.GET.get('api_key')
        
        if not api_key:
            return JsonResponse({
                'error': 'API key required',
                'message': 'API key is required for this endpoint'
            }, status=401)
        
        # Find tenant by API key
        try:
            tenant = Tenant.objects.get(api_key=api_key, is_active=True, is_deleted=False)
            request.tenant = tenant
        except Tenant.DoesNotExist:
            return JsonResponse({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid'
            }, status=401)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def tenant_webhook_signature_required(view_func: Callable) -> Callable:
    """
    Decorator to require valid webhook signature.
    
    This decorator checks for a valid webhook signature for security.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        # Get signature from headers
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
        if not signature:
            return JsonResponse({
                'error': 'Signature required',
                'message': 'Webhook signature is required'
            }, status=401)
        
        # Verify signature
        if not tenant_security_service.verify_webhook_signature(
            tenant, request.body, signature
        ):
            return JsonResponse({
                'error': 'Invalid signature',
                'message': 'Webhook signature verification failed'
            }, status=401)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Class method decorators
def method_tenant_required(method: Callable) -> Callable:
    """Decorator for class methods requiring tenant context."""
    @functools.wraps(method)
    def wrapper(self, request, *args, **kwargs):
        if not hasattr(request, 'tenant') or not request.tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        return method(self, request, *args, **kwargs)
    
    return wrapper


def method_tenant_owner_required(method: Callable) -> Callable:
    """Decorator for class methods requiring tenant ownership."""
    @functools.wraps(method)
    def wrapper(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'message': 'You must be logged in to perform this action'
            }, status=401)
        
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=400)
        
        if not (request.user.is_superuser or tenant.owner == request.user):
            return JsonResponse({
                'error': 'Access denied',
                'message': TENANT_ERROR_MESSAGES['access_denied']
            }, status=403)
        
        return method(self, request, *args, **kwargs)
    
    return wrapper


# DRF API decorators
def api_tenant_required(view_func: Callable) -> Callable:
    """DRF API view decorator for tenant context."""
    @api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    @permission_classes([IsAuthenticated])
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'tenant') or not request.tenant:
            return Response({
                'error': 'Tenant context required',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def api_tenant_owner_required(view_func: Callable) -> Callable:
    """DRF API view decorator for tenant ownership."""
    @api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    @permission_classes([IsAuthenticated, IsTenantOwner])
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Utility decorators
def handle_tenant_exceptions(view_func: Callable) -> Callable:
    """
    Decorator to handle tenant-specific exceptions.
    
    This decorator catches common tenant-related exceptions
    and returns appropriate error responses.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Tenant.DoesNotExist:
            return JsonResponse({
                'error': 'Tenant not found',
                'message': TENANT_ERROR_MESSAGES['tenant_not_found']
            }, status=404)
        except PermissionError:
            return JsonResponse({
                'error': 'Permission denied',
                'message': TENANT_ERROR_MESSAGES['access_denied']
            }, status=403)
        except ValueError as e:
            return JsonResponse({
                'error': 'Invalid input',
                'message': str(e)
            }, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in {view_func.__name__}: {e}")
            return JsonResponse({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }, status=500)
    
    return wrapper


def validate_tenant_data(required_fields: list = None):
    """
    Decorator to validate tenant data in request.
    
    Args:
        required_fields: List of required field names
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    data = request.POST if request.content_type == 'application/x-www-form-urlencoded' else request.data
                except AttributeError:
                    data = request.POST
                
                # Check required fields
                if required_fields:
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return JsonResponse({
                            'error': 'Missing required fields',
                            'message': f'Required fields: {", ".join(missing_fields)}'
                        }, status=400)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Combined decorators for common use cases
def tenant_endpoint(view_func: Callable) -> Callable:
    """Combined decorator for standard tenant endpoints."""
    return (
        login_required(view_func) and
        tenant_required(view_func) and
        tenant_active_required(view_func) and
        handle_tenant_exceptions(view_func)
    )


def tenant_admin_endpoint(view_func: Callable) -> Callable:
    """Combined decorator for tenant admin endpoints."""
    return (
        login_required(view_func) and
        tenant_required(view_func) and
        tenant_owner_required(view_func) and
        tenant_active_required(view_func) and
        handle_tenant_exceptions(view_func)
    )


def tenant_api_endpoint(view_func: Callable) -> Callable:
    """Combined decorator for tenant API endpoints."""
    return (
        api_tenant_required(view_func) and
        tenant_active_required(view_func) and
        handle_tenant_exceptions(view_func)
    )


def tenant_admin_api_endpoint(view_func: Callable) -> Callable:
    """Combined decorator for tenant admin API endpoints."""
    return (
        api_tenant_owner_required(view_func) and
        tenant_active_required(view_func) and
        handle_tenant_exceptions(view_func)
    )

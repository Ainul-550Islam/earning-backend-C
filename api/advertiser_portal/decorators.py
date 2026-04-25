"""
View Decorators for Advertiser Portal

This module contains custom decorators for views and API endpoints
including authentication, permissions, caching, rate limiting, and logging.
"""

import functools
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from django.core.cache import cache
from django.http import JsonResponse, HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models.advertiser import Advertiser
from .permissions import *
from .exceptions import *
from .utils import *

logger = logging.getLogger(__name__)


def advertiser_required(view_func: Callable) -> Callable:
    """
    Decorator to require advertiser authentication.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Authentication required',
                    'message': 'Please log in to access this resource.'
                }, status=401)
            else:
                messages.error(request, 'Please log in to access this resource.')
                return redirect('login')
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            if not advertiser.is_active:
                if request.accepts('application/json'):
                    return JsonResponse({
                        'error': 'Account inactive',
                        'message': 'Your advertiser account is currently inactive.'
                    }, status=403)
                else:
                    messages.error(request, 'Your advertiser account is currently inactive.')
                    return redirect('dashboard')
            
            # Add advertiser to request object
            request.advertiser = advertiser
            return view_func(request, *args, **kwargs)
            
        except Advertiser.DoesNotExist:
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Advertiser not found',
                    'message': 'No advertiser account found for this user.'
                }, status=404)
            else:
                messages.error(request, 'No advertiser account found for this user.')
                return redirect('dashboard')
    
    return wrapper


def verified_advertiser_required(view_func: Callable) -> Callable:
    """
    Decorator to require verified advertiser status.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'advertiser'):
            return advertiser_required(view_func)(request, *args, **kwargs)
        
        if request.advertiser.verification_status != 'verified':
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Account not verified',
                    'message': 'Your advertiser account must be verified to access this resource.'
                }, status=403)
            else:
                messages.error(request, 'Your advertiser account must be verified to access this resource.')
                return redirect('verification')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def active_campaign_required(view_func: Callable) -> Callable:
    """
    Decorator to require at least one active campaign.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'advertiser'):
            return verified_advertiser_required(view_func)(request, *args, **kwargs)
        
        from .models.campaign import AdCampaign
        active_campaigns = AdCampaign.objects.filter(
            advertiser=request.advertiser,
            status='active'
        ).count()
        
        if active_campaigns == 0:
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'No active campaigns',
                    'message': 'You must have at least one active campaign to access this resource.'
                }, status=403)
            else:
                messages.error(request, 'You must have at least one active campaign to access this resource.')
                return redirect('campaigns')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def sufficient_balance_required(min_balance: float = 0.0) -> Callable:
    """
    Decorator to require sufficient wallet balance.
    
    Args:
        min_balance: Minimum required balance
        
    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'advertiser'):
                return verified_advertiser_required(view_func)(request, *args, **kwargs)
            
            wallet = getattr(request.advertiser, 'wallet', None)
            if not wallet or wallet.balance < min_balance:
                if request.accepts('application/json'):
                    return JsonResponse({
                        'error': 'Insufficient balance',
                        'message': f'Your wallet balance must be at least ${min_balance:.2f} to access this resource.',
                        'current_balance': float(wallet.balance) if wallet else 0.0,
                        'required_balance': min_balance
                    }, status=403)
                else:
                    messages.error(request, f'Your wallet balance must be at least ${min_balance:.2f} to access this resource.')
                    return redirect('billing')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def rate_limit(limit: int, window: int = 3600, key_func: Optional[Callable] = None) -> Callable:
    """
    Decorator for rate limiting API endpoints.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func(request)
            elif hasattr(request, 'user') and request.user.is_authenticated:
                key = f"rate_limit:{request.user.id}:{request.path}"
            else:
                key = f"rate_limit:anonymous:{request.META.get('REMOTE_ADDR', 'unknown')}:{request.path}"
            
            # Check rate limit
            current_count = cache.get(key, 0)
            if current_count >= limit:
                if request.accepts('application/json'):
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'message': f'Rate limit of {limit} requests per {window} seconds exceeded.',
                        'retry_after': window
                    }, status=429)
                else:
                    messages.error(request, f'Rate limit exceeded. Please try again later.')
                    return redirect('dashboard')
            
            # Increment counter
            cache.set(key, current_count + 1, window)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def api_cache(timeout: int = 300, key_func: Optional[Callable] = None) -> Callable:
    """
    Decorator for caching API responses.
    
    Args:
        timeout: Cache timeout in seconds
        key_func: Function to generate cache key
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(request)
            else:
                # Generate key from URL and user
                key_parts = [request.path]
                if hasattr(request, 'user') and request.user.is_authenticated:
                    key_parts.append(str(request.user.id))
                key = f"api_cache:{':'.join(key_parts)}"
            
            # Check cache
            cached_response = cache.get(key)
            if cached_response:
                return JsonResponse(cached_response)
            
            # Execute view and cache response
            response = view_func(request, *args, **kwargs)
            
            if hasattr(response, 'status_code') and response.status_code == 200:
                try:
                    if hasattr(response, 'data'):
                        cache.set(key, response.data, timeout)
                    else:
                        cache.set(key, response.content, timeout)
                except Exception as e:
                    logger.warning(f"Failed to cache API response: {e}")
            
            return response
        
        return wrapper
    return decorator


def log_api_calls(view_func: Callable) -> Callable:
    """
    Decorator for logging API calls.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        
        # Log request
        log_data = {
            'method': request.method,
            'path': request.path,
            'user_id': getattr(request.user, 'id', None),
            'advertiser_id': getattr(request.advertiser, 'id', None) if hasattr(request, 'advertiser') else None,
            'timestamp': datetime.now().isoformat(),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        try:
            response = view_func(request, *args, **kwargs)
            
            # Log response
            end_time = time.time()
            log_data.update({
                'status_code': getattr(response, 'status_code', 200),
                'response_time_ms': int((end_time - start_time) * 1000),
                'success': True
            })
            
            logger.info(f"API Call: {log_data}")
            
            return response
            
        except Exception as e:
            # Log error
            log_data.update({
                'error': str(e),
                'success': False
            })
            
            logger.error(f"API Call Error: {log_data}")
            
            raise
    
    return wrapper


def handle_exceptions(view_func: Callable) -> Callable:
    """
    Decorator for handling exceptions in views.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        
        except BaseAdvertiserPortalException as e:
            # Handle custom exceptions
            if request.accepts('application/json'):
                return JsonResponse(e.to_dict(), status=400)
            else:
                messages.error(request, e.message)
                return redirect('dashboard')
        
        except ValidationError as e:
            # Handle validation errors
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Validation Error',
                    'message': str(e),
                    'details': getattr(e, 'error_dict', {})
                }, status=400)
            else:
                messages.error(request, str(e))
                return redirect(request.path)
        
        except PermissionDenied as e:
            # Handle permission errors
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Permission Denied',
                    'message': 'You do not have permission to access this resource.'
                }, status=403)
            else:
                messages.error(request, 'You do not have permission to access this resource.')
                return redirect('dashboard')
        
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in {view_func.__name__}: {e}", exc_info=True)
            
            if request.accepts('application/json'):
                return JsonResponse({
                    'error': 'Internal Server Error',
                    'message': 'An unexpected error occurred. Please try again later.'
                }, status=500)
            else:
                messages.error(request, 'An unexpected error occurred. Please try again later.')
                return redirect('dashboard')
    
    return wrapper


def atomic_transaction(view_func: Callable) -> Callable:
    """
    Decorator for running views in atomic transactions.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        with transaction.atomic():
            return view_func(request, *args, **kwargs)
    
    return wrapper


def require_permissions(*permissions: str) -> Callable:
    """
    Decorator for requiring specific permissions.
    
    Args:
        permissions: List of required permissions
        
    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'advertiser'):
                return advertiser_required(view_func)(request, *args, **kwargs)
            
            user_permissions = get_advertiser_permissions(request.user)
            
            for permission in permissions:
                if permission not in user_permissions:
                    if request.accepts('application/json'):
                        return JsonResponse({
                            'error': 'Permission Denied',
                            'message': f'Permission "{permission}" is required to access this resource.'
                        }, status=403)
                    else:
                        messages.error(request, f'Permission "{permission}" is required to access this resource.')
                        return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_feature_flag(feature_flag: str) -> Callable:
    """
    Decorator for requiring specific feature flags.
    
    Args:
        feature_flag: Feature flag name
        
    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if feature flag is enabled
            from .config import config_manager
            dynamic_config = config_manager.get_dynamic_config()
            
            if not dynamic_config.get_feature_flag(feature_flag):
                if request.accepts('application/json'):
                    return JsonResponse({
                        'error': 'Feature Disabled',
                        'message': f'The feature "{feature_flag}" is currently disabled.'
                    }, status=503)
                else:
                    messages.error(request, f'The feature "{feature_flag}" is currently disabled.')
                    return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def validate_request_data(serializer_class: type) -> Callable:
    """
    Decorator for validating request data with serializer.
    
    Args:
        serializer_class: Serializer class for validation
        
    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                serializer = serializer_class(data=request.data)
                if not serializer.is_valid():
                    if request.accepts('application/json'):
                        return JsonResponse({
                            'error': 'Validation Error',
                            'message': 'Request data validation failed.',
                            'errors': serializer.errors
                        }, status=400)
                    else:
                        for field, errors in serializer.errors.items():
                            for error in errors:
                                messages.error(request, f"{field}: {error}")
                        return redirect(request.path)
                
                # Add validated data to request
                request.validated_data = serializer.validated_data
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# DRF-specific decorators
def drf_advertiser_required(view_func: Callable) -> Callable:
    """
    DRF-specific decorator for advertiser authentication.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @api_view(['GET', 'POST', 'PUT', 'DELETE'])
    @permission_classes([IsAuthenticated])
    @authentication_classes([TokenAuthentication])
    @log_api_calls
    @handle_exceptions
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            if not advertiser.is_active:
                return Response({
                    'error': 'Account inactive',
                    'message': 'Your advertiser account is currently inactive.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            request.advertiser = advertiser
            return view_func(request, *args, **kwargs)
            
        except Advertiser.DoesNotExist:
            return Response({
                'error': 'Advertiser not found',
                'message': 'No advertiser account found for this user.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return wrapper


def drf_verified_required(view_func: Callable) -> Callable:
    """
    DRF-specific decorator for verified advertiser requirement.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'advertiser'):
            return drf_advertiser_required(view_func)(request, *args, **kwargs)
        
        if request.advertiser.verification_status != 'verified':
            return Response({
                'error': 'Account not verified',
                'message': 'Your advertiser account must be verified to access this resource.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Composite decorators
def api_endpoint(view_func: Callable) -> Callable:
    """
    Composite decorator for standard API endpoints.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    return drf_verified_required(
        log_api_calls(
            handle_exceptions(
                rate_limit(1000, 3600)(
                    view_func
                )
            )
        )
    )


def sensitive_api_endpoint(view_func: Callable) -> Callable:
    """
    Composite decorator for sensitive API endpoints.
    
    Args:
        view_func: The view function to decorate
        
    Returns:
        Decorated view function
    """
    return drf_verified_required(
        log_api_calls(
            handle_exceptions(
                atomic_transaction(
                    rate_limit(100, 3600)(
                        view_func
                    )
                )
            )
        )
    )


# Export all decorators
__all__ = [
    'advertiser_required',
    'verified_advertiser_required',
    'active_campaign_required',
    'sufficient_balance_required',
    'rate_limit',
    'api_cache',
    'log_api_calls',
    'handle_exceptions',
    'atomic_transaction',
    'require_permissions',
    'require_feature_flag',
    'validate_request_data',
    'drf_advertiser_required',
    'drf_verified_required',
    'api_endpoint',
    'sensitive_api_endpoint',
]

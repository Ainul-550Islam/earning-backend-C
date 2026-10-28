# api/admin_panel/decorators.py
"""
Decorators for admin_panel views, viewsets, tasks, signals.
"""
from __future__ import annotations
import functools
import logging
import time
from typing import Callable, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def require_admin_role(*roles):
    """
    ViewSet method decorator: require specific admin role.
    Roles: superadmin, admin, moderator, finance, analyst, support, viewer

    @require_admin_role('superadmin', 'admin')
    def approve_withdrawal(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            try:
                from api.admin_panel.INTEGRATION_SYSTEM.auth_bridge import AuthBridge
                role = AuthBridge.get_admin_role(request.user)
                if role not in roles and 'superadmin' not in roles:
                    from rest_framework.response import Response
                    return Response(
                        {'error': f'Role "{role}" cannot perform this action. Required: {roles}'},
                        status=403
                    )
            except Exception as e:
                logger.debug(f"[require_admin_role] check failed: {e}")
            return func(view, request, *args, **kwargs)
        return wrapper
    return decorator


def cache_response(ttl: int = 60, key_prefix: str = ''):
    """
    Cache a ViewSet action response.

    @cache_response(ttl=300, key_prefix='dashboard')
    def stats(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            query_str = request.query_params.urlencode()
            cache_key = f'admin_panel:view:{key_prefix or func.__name__}:{hash(query_str)}'
            cached = cache.get(cache_key)
            if cached is not None:
                from rest_framework.response import Response
                return Response({'success': True, 'data': cached, 'from_cache': True})
            response = func(view, request, *args, **kwargs)
            if hasattr(response, 'data') and response.data.get('success'):
                cache.set(cache_key, response.data.get('data'), ttl)
            return response
        return wrapper
    return decorator


def log_admin_action(action: str, model: str = ''):
    """
    Auto-log admin action to AdminActivity.

    @log_admin_action('approve_withdrawal', model='PayoutItem')
    def approve(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            start = time.monotonic()
            response = func(view, request, *args, **kwargs)
            duration_ms = int((time.monotonic() - start) * 1000)
            success = getattr(response, 'status_code', 200) < 400
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user,
                    action=action,
                    model_name=model,
                    changes={'duration_ms': duration_ms},
                    status='success' if success else 'failed',
                    ip=request.META.get('REMOTE_ADDR', ''),
                    method=request.method,
                    path=request.path,
                    response_code=getattr(response, 'status_code', 0),
                )
            except Exception as e:
                logger.debug(f"[log_admin_action] {e}")
            return response
        return wrapper
    return decorator


def superadmin_only(func: Callable) -> Callable:
    """Only superadmin can call this endpoint."""
    @functools.wraps(func)
    def wrapper(view, request, *args, **kwargs):
        if not request.user.is_superuser:
            from rest_framework.response import Response
            return Response({'error': 'Superadmin access required'}, status=403)
        return func(view, request, *args, **kwargs)
    return wrapper


def rate_limit(calls: int = 10, period: int = 60, scope: str = 'user'):
    """
    Simple rate limiter for admin endpoints.

    @rate_limit(calls=5, period=60, scope='user')
    def trigger_training(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            if scope == 'user':
                key = f'admin_panel:rate:{func.__name__}:user:{request.user.pk}'
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')
                key = f'admin_panel:rate:{func.__name__}:ip:{ip}'

            current = cache.get(key, 0)
            if current >= calls:
                from rest_framework.response import Response
                return Response(
                    {'error': f'Rate limit exceeded. Max {calls} calls per {period}s.'},
                    status=429
                )
            cache.set(key, current + 1, period)
            return func(view, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_payload(*required_fields):
    """
    Validate required fields in request.data.

    @validate_payload('user_id', 'amount', 'reason')
    def adjust_balance(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            missing = [f for f in required_fields if not request.data.get(f)]
            if missing:
                from rest_framework.response import Response
                return Response(
                    {'error': f'Missing required fields: {missing}'},
                    status=400
                )
            return func(view, request, *args, **kwargs)
        return wrapper
    return decorator


def feature_flag_required(flag_key: str):
    """
    Only execute if feature flag is enabled.

    @feature_flag_required('ai_recommendations')
    def get_recommendations(self, request):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(view, request, *args, **kwargs):
            try:
                from api.admin_panel.services.FeatureFlagService import FeatureFlagService
                if not FeatureFlagService.is_enabled(flag_key):
                    from rest_framework.response import Response
                    return Response(
                        {'error': f'Feature "{flag_key}" is not enabled'},
                        status=403
                    )
            except Exception:
                pass
            return func(view, request, *args, **kwargs)
        return wrapper
    return decorator


def handle_integration_errors(func: Callable) -> Callable:
    """Wrap integration calls with graceful error handling."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[Integration] {func.__name__} failed: {e}")
            from rest_framework.response import Response
            return Response({'success': False, 'error': str(e)}, status=500)
    return wrapper
# api/referral/decorators.py
# Decorators for referral views, services, tasks
# ============================================================

import logging
import functools
from typing import Callable
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def referral_program_active(view_func: Callable) -> Callable:
    """
    Decorator: returns 503 if referral program is inactive.
    Use on user-facing referral endpoints.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            from django.core.cache import cache
            settings = cache.get('referral_settings')
            if not settings:
                from api.referral.models import ReferralSettings
                settings = ReferralSettings.objects.first()
            if settings and not settings.is_active:
                return JsonResponse(
                    {'error': 'Referral program is currently inactive.', 'code': 'program_inactive'},
                    status=503
                )
        except Exception as e:
            logger.debug(f'[Decorator] referral_program_active check failed: {e}')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_referral_admin(view_func: Callable) -> Callable:
    """
    Decorator: requires referral admin permission.
    Use on admin-only endpoints.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return JsonResponse({'error': 'Authentication required.'}, status=401)
        if not (user.is_staff or user.is_superuser or
                user.groups.filter(name='referral_admin').exists()):
            return JsonResponse({'error': 'Referral admin access required.'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def track_referral_click(view_func: Callable) -> Callable:
    """
    Decorator: automatically track referral code click on redirect views.
    """
    @functools.wraps(view_func)
    def wrapper(request, code=None, *args, **kwargs):
        if code:
            try:
                from api.referral.services.ReferralCodeService import ReferralCodeService
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                ReferralCodeService.track_click(code_value=code, ip=ip)
            except Exception as e:
                logger.debug(f'[Decorator] track_referral_click failed: {e}')
        return view_func(request, code=code, *args, **kwargs)
    return wrapper


def rate_limit_referral(max_per_hour: int = 100):
    """
    Decorator factory: limits referral endpoint calls per user per hour.
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if user and user.is_authenticated and not user.is_staff:
                try:
                    from django.core.cache import cache
                    cache_key = f'referral_ratelimit:{user.id}:{view_func.__name__}'
                    count = cache.get(cache_key, 0)
                    if count >= max_per_hour:
                        return JsonResponse(
                            {'error': 'Rate limit exceeded.', 'code': 'rate_limit'},
                            status=429
                        )
                    cache.set(cache_key, count + 1, timeout=3600)
                except Exception as e:
                    logger.debug(f'[Decorator] rate_limit_referral failed: {e}')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def log_referral_action(action_name: str):
    """
    Decorator factory: logs referral actions to audit log.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
                request = next((a for a in args if hasattr(a, 'user')), None)
                user = getattr(request, 'user', None) if request else None
                ReferralAuditLogger.log(action=action_name, user=user, data={})
            except Exception:
                pass
            return result
        return wrapper
    return decorator


def cache_referral_response(timeout: int = 60):
    """
    Decorator: caches view response in Django cache.
    Use on public endpoints (leaderboard, stats).
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            cache_key = f'referral_view:{view_func.__name__}:{request.path}:{getattr(request.user, "id", "anon")}'
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            response = view_func(request, *args, **kwargs)
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(cache_key, response, timeout=timeout)
            return response
        return wrapper
    return decorator


def fraud_check_required(view_func: Callable) -> Callable:
    """
    Decorator: runs fraud check on the requesting user before allowing action.
    Blocks if user has high fraud risk score.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_staff:
            try:
                from api.referral.INTEGRATION_SYSTEM.integ_adapter import FraudAdapter
                if FraudAdapter.is_high_risk_user(user, threshold=0.8):
                    return JsonResponse(
                        {'error': 'Access restricted due to account risk level.', 'code': 'high_risk'},
                        status=403
                    )
            except Exception:
                pass
        return view_func(request, *args, **kwargs)
    return wrapper
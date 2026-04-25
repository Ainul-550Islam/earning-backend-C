# earning_backend/api/notifications/decorators.py
"""
Decorators — Reusable function/method decorators for the notification system.

Covers:
  - Rate limiting          (@rate_limit)
  - Retry logic            (@retry_on_failure)
  - Fatigue checking       (@check_fatigue)
  - Opt-out checking       (@check_opt_out)
  - Performance timing     (@track_performance)
  - Audit logging          (@audit_action)
  - Feature flag gating    (@require_feature)
  - Cache result           (@cache_notification_result)
  - Admin only             (@admin_required)
  - Notification ownership (@owns_notification)
"""

import functools
import logging
import time
from typing import Callable, Optional

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limit decorator
# ---------------------------------------------------------------------------

def rate_limit(key_prefix: str, limit: int = 10, window: int = 60):
    """
    Limit how many times a view or function can be called within `window` seconds.

    Usage:
        @rate_limit('send_push', limit=5, window=60)
        def send_push_notification(request, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from request user or IP
            request = next((a for a in args if hasattr(a, 'user')), None)
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                identity = f'user_{request.user.pk}'
            elif request:
                identity = f'ip_{request.META.get("REMOTE_ADDR", "unknown")}'
            else:
                identity = 'global'

            cache_key = f'rl:{key_prefix}:{identity}'
            current = cache.get(cache_key, 0)

            if current >= limit:
                logger.warning(f'Rate limit exceeded: {cache_key}')
                if request:
                    return JsonResponse(
                        {'error': 'Rate limit exceeded. Try again later.',
                         'code': 'RATE_LIMIT_EXCEEDED', 'retry_after': window},
                        status=429,
                    )
                raise Exception(f'Rate limit exceeded for {key_prefix}')

            # Increment counter
            if current == 0:
                cache.set(cache_key, 1, window)
            else:
                cache.incr(cache_key)

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Retry on failure
# ---------------------------------------------------------------------------

def retry_on_failure(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_failure: Optional[Callable] = None,
):
    """
    Retry a function on failure with exponential backoff.

    Usage:
        @retry_on_failure(max_retries=3, delay_seconds=1, backoff_factor=2)
        def send_fcm_push(token, payload):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = delay_seconds
            last_exc = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        logger.warning(
                            f'{func.__name__}: attempt {attempt}/{max_retries} failed: {exc}. '
                            f'Retrying in {delay:.1f}s...'
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f'{func.__name__}: all {max_retries} attempts failed: {exc}')

            if on_failure:
                try:
                    return on_failure(last_exc, *args, **kwargs)
                except Exception:
                    pass
            raise last_exc
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Fatigue check
# ---------------------------------------------------------------------------

def check_fatigue(priority: str = 'medium', bypass_priorities: tuple = ('critical', 'urgent')):
    """
    Skip execution if the target user is notification-fatigued.

    The decorated function must receive `user` as first positional arg
    or as a keyword argument.

    Usage:
        @check_fatigue(priority='medium')
        def send_marketing_push(user, notification):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get('user') or (args[0] if args else None)

            if user and hasattr(user, 'pk'):
                notif_priority = kwargs.get('priority', priority)
                if notif_priority not in bypass_priorities:
                    try:
                        from api.notifications.services.FatigueService import fatigue_service
                        if fatigue_service.is_fatigued(user, priority=notif_priority):
                            logger.info(
                                f'check_fatigue: user #{user.pk} is fatigued — '
                                f'skipping {func.__name__}'
                            )
                            return {
                                'success': False,
                                'skipped': True,
                                'reason': 'user_fatigued',
                            }
                    except Exception as exc:
                        logger.debug(f'check_fatigue: {exc}')

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Opt-out check
# ---------------------------------------------------------------------------

def check_opt_out(channel: str = 'in_app'):
    """
    Skip execution if the target user has opted out of the channel.

    Usage:
        @check_opt_out(channel='email')
        def send_email_notification(user, notification):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get('user') or (args[0] if args else None)
            notif_channel = kwargs.get('channel', channel)

            if user and hasattr(user, 'pk'):
                try:
                    from api.notifications.services.OptOutService import opt_out_service
                    if opt_out_service.is_opted_out(user, notif_channel):
                        logger.info(
                            f'check_opt_out: user #{user.pk} opted out of '
                            f'{notif_channel} — skipping {func.__name__}'
                        )
                        return {
                            'success': False,
                            'skipped': True,
                            'reason': f'opted_out_{notif_channel}',
                        }
                except Exception as exc:
                    logger.debug(f'check_opt_out: {exc}')

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Performance timing
# ---------------------------------------------------------------------------

def track_performance(operation: str = '', service: str = 'notifications'):
    """
    Track function execution time and record it in the performance monitor.

    Usage:
        @track_performance(operation='send_push', service='fcm')
        def _send_fcm(token, payload):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            start = time.monotonic()
            success = True
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict):
                    success = result.get('success', True)
                return result
            except Exception as exc:
                success = False
                raise exc
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000
                try:
                    from api.notifications.integration_system.performance_monitor import performance_monitor
                    performance_monitor.record(op_name, elapsed_ms, success, service)
                except Exception:
                    pass
                if elapsed_ms > 2000:
                    logger.warning(
                        f'SLOW: {service}.{op_name} took {elapsed_ms:.0f}ms'
                    )
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def audit_action(action: str, module: str = 'notifications'):
    """
    Log every call to the audit trail.

    Usage:
        @audit_action(action='send', module='notifications')
        def send_notification(request, pk):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = next((a for a in args if hasattr(a, 'user')), None)
            actor_id = getattr(getattr(request, 'user', None), 'pk', None) if request else None

            result = None
            success = True
            error = ''
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                success = False
                error = str(exc)
                raise exc
            finally:
                try:
                    from api.notifications.integration_system.integ_audit_logs import audit_logger
                    audit_logger.log(
                        action=action,
                        module=module,
                        actor_id=actor_id,
                        success=success,
                        error=error,
                        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR', '') if request else '',
                    )
                except Exception:
                    pass
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def require_feature(flag_name: str, default: bool = True):
    """
    Gate a view or function behind a feature flag.

    Checks Django settings.NOTIFICATION_FEATURES dict.

    Usage:
        @require_feature('ENABLE_PUSH_NOTIFICATIONS')
        def send_push(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.conf import settings
            features = getattr(settings, 'NOTIFICATION_FEATURES', {})
            enabled = features.get(flag_name, default)

            if not enabled:
                request = next((a for a in args if hasattr(a, 'user')), None)
                if request:
                    return JsonResponse(
                        {'error': f'Feature {flag_name} is currently disabled.'},
                        status=503,
                    )
                raise Exception(f'Feature {flag_name} is disabled')
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Cache result
# ---------------------------------------------------------------------------

def cache_notification_result(key_template: str, ttl: int = 300):
    """
    Cache the return value of a function.

    key_template may contain {arg0}, {arg1}, {user_id} placeholders.

    Usage:
        @cache_notification_result('unread_count:{user_id}', ttl=60)
        def get_unread_count(user_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                fmt_kwargs = {f'arg{i}': a for i, a in enumerate(args)}
                fmt_kwargs.update(kwargs)
                cache_key = key_template.format(**fmt_kwargs)
            except (KeyError, IndexError):
                cache_key = f'{func.__name__}:{hash(str(args)+str(kwargs))}'

            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            try:
                cache.set(cache_key, result, ttl)
            except Exception:
                pass
            return result
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Ownership check (DRF view methods)
# ---------------------------------------------------------------------------

def owns_notification(func: Callable) -> Callable:
    """
    Ensure the requesting user owns the notification being accessed.
    Meant for DRF view actions that take `pk` as argument.

    Usage:
        @owns_notification
        def mark_read(self, request, pk=None):
            ...
    """
    @functools.wraps(func)
    def wrapper(self, request, pk=None, *args, **kwargs):
        try:
            from api.notifications.models import Notification
            notif = Notification.objects.get(pk=pk)
            if notif.user != request.user and not request.user.is_staff:
                return JsonResponse(
                    {'error': 'You do not have permission to access this notification.'},
                    status=403,
                )
        except Exception:
            return JsonResponse({'error': 'Notification not found.'}, status=404)
        return func(self, request, pk=pk, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Admin required (non-DRF views)
# ---------------------------------------------------------------------------

def notification_admin_required(func: Callable) -> Callable:
    """
    Restrict a view to staff/admin users only.

    Usage:
        @notification_admin_required
        def bulk_send_view(request):
            ...
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required.'}, status=401)
        if not request.user.is_staff:
            return JsonResponse({'error': 'Staff access required.'}, status=403)
        return func(request, *args, **kwargs)
    return wrapper

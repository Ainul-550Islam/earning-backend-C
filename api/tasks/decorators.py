"""
api/tasks/decorators.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Decorators for task views, Celery tasks, and service methods.
"""

import logging
import time
import functools
import hashlib
from typing import Callable, Optional, Any
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CELERY TASK DECORATORS
# ══════════════════════════════════════════════════════════════════════════════

def task_with_circuit_breaker(failure_threshold: int = 5, reset_timeout: int = 300):
    """
    Decorator for Celery task functions that implements a circuit breaker.
    After `failure_threshold` consecutive failures, the circuit opens
    and skips execution for `reset_timeout` seconds.

    Usage:
        @shared_task(bind=True)
        @task_with_circuit_breaker(failure_threshold=5, reset_timeout=300)
        def my_task(self, ...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            task_name = func.__name__
            cb_key    = f'circuit_breaker_{task_name}'
            fail_key  = f'circuit_failures_{task_name}'

            # Check if circuit is open
            if cache.get(cb_key) == 'open':
                logger.warning(f"[CIRCUIT BREAKER] {task_name} — circuit open, skipping.")
                return {'status': 'skipped', 'reason': 'circuit_breaker_open'}

            try:
                result = func(self, *args, **kwargs)
                # Success — reset failure counter
                cache.delete(fail_key)
                return result
            except Exception as exc:
                # Increment failure counter
                failures = (cache.get(fail_key) or 0) + 1
                cache.set(fail_key, failures, timeout=reset_timeout)

                if failures >= failure_threshold:
                    # Open circuit
                    cache.set(cb_key, 'open', timeout=reset_timeout)
                    logger.error(
                        f"[CIRCUIT BREAKER] {task_name} — circuit OPENED "
                        f"after {failures} failures."
                    )
                raise exc
        return wrapper
    return decorator


def task_idempotent(ttl: int = 3600):
    """
    Decorator that ensures a Celery task with the same arguments
    is not executed more than once within the TTL window.

    Usage:
        @shared_task(bind=True)
        @task_idempotent(ttl=3600)
        def my_task(self, user_id, offer_id): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            idem_key = f"idempotent_{hashlib.sha256(key_data.encode()).hexdigest()}"
            if cache.get(idem_key):
                logger.info(f"[IDEMPOTENT] {func.__name__} already executed, skipping.")
                return {'status': 'skipped', 'reason': 'already_executed'}
            cache.set(idem_key, 1, timeout=ttl)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def task_with_lock(timeout: int = 300, blocking: bool = False):
    """
    Distributed lock decorator for Celery tasks.
    Prevents concurrent execution of the same task.

    Usage:
        @shared_task(bind=True)
        @task_with_lock(timeout=300)
        def my_task(self, batch_id): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            lock_key = f"task_lock_{func.__name__}"
            if not blocking:
                if not cache.add(lock_key, self.request.id, timeout=timeout):
                    logger.info(f"[LOCK] {func.__name__} already running, skipping.")
                    return {'status': 'skipped', 'reason': 'already_running'}
            try:
                return func(self, *args, **kwargs)
            finally:
                cache.delete(lock_key)
        return wrapper
    return decorator


def task_timed(log_level: str = 'INFO'):
    """
    Logs execution time for a Celery task function.

    Usage:
        @shared_task(bind=True)
        @task_timed()
        def my_task(self): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            start  = time.monotonic()
            result = func(self, *args, **kwargs)
            elapsed = time.monotonic() - start
            log_fn = getattr(logger, log_level.lower(), logger.info)
            log_fn(f"[TIMED] {func.__name__} completed in {elapsed:.3f}s")
            return result
        return wrapper
    return decorator


def task_emit_event(event: str, payload_fn: Callable = None):
    """
    Emit an EventBus event after a task completes successfully.

    Usage:
        @shared_task(bind=True)
        @task_emit_event('task.completed', payload_fn=lambda result: result)
        def complete_task(self, user_id, task_id): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            if isinstance(result, dict) and result.get('status') in ('success', 'credited'):
                try:
                    from api.tasks.integration.event_bus import EventBus
                    payload = payload_fn(result) if payload_fn else result
                    EventBus.emit(event, payload, async_dispatch=True)
                except Exception as e:
                    logger.debug(f"[EVENT EMIT] {event}: {e}")
            return result
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# VIEW / API DECORATORS
# ══════════════════════════════════════════════════════════════════════════════

def require_task_permission(permission: str):
    """
    DRF view decorator that checks a specific task permission.

    Usage:
        @require_task_permission('tasks.manage_tasks')
        def my_view(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm(permission):
                return Response(
                    {'error': 'Permission denied', 'required': permission},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_verified_email(func):
    """
    Checks that the requesting user has a verified email address.

    Usage:
        @require_verified_email
        def complete_task(request, task_id): ...
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)
        # Check email verification
        try:
            if not user.emailaddress_set.filter(verified=True).exists():
                return Response(
                    {'error': 'Email verification required.', 'code': 'email_not_verified'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Exception:
            pass  # If allauth not installed, skip
        return func(request, *args, **kwargs)
    return wrapper


def require_kyc(tier: str = 'basic'):
    """
    Checks that the user has the required KYC tier.

    Usage:
        @require_kyc(tier='standard')
        def withdraw_funds(request): ...
    """
    TIER_ORDER = {'none': 0, 'basic': 1, 'standard': 2, 'full': 3, 'edd': 4}

    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache as _cache
            user_id = getattr(request.user, 'pk', None)
            if not user_id:
                return Response({'error': 'Authentication required.'}, status=401)

            current_tier = _cache.get(f'kyc_tier_{user_id}', 'none')
            required_level  = TIER_ORDER.get(tier, 1)
            current_level   = TIER_ORDER.get(current_tier, 0)

            if current_level < required_level:
                return Response(
                    {
                        'error': f'KYC verification required (minimum: {tier}).',
                        'code':  'kyc_required',
                        'required_tier': tier,
                        'current_tier':  current_tier,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def rate_limit_task_action(limit: int = 10, window: int = 60, key_fn: Callable = None):
    """
    Rate-limit a view action per user or custom key.

    Args:
        limit:  Max requests allowed within `window` seconds.
        window: Time window in seconds.
        key_fn: Function to generate the rate-limit key from request.
                Defaults to user ID.

    Usage:
        @rate_limit_task_action(limit=5, window=60)
        def submit_task(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if key_fn:
                key = key_fn(request)
            else:
                user_id = getattr(request.user, 'pk', None) or request.META.get('REMOTE_ADDR')
                key = f'rl_{func.__name__}_{user_id}'

            count = cache.get(key, 0)
            if count >= limit:
                return Response(
                    {
                        'error': 'Rate limit exceeded.',
                        'code':  'rate_limited',
                        'retry_after': window,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            cache.set(key, count + 1, timeout=window)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def cache_response(ttl: int = 300, key_fn: Callable = None, vary_on_user: bool = True):
    """
    Cache a DRF view's response in Redis.

    Usage:
        @cache_response(ttl=60, vary_on_user=True)
        def task_list(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if key_fn:
                cache_key = key_fn(request, *args, **kwargs)
            else:
                parts = [func.__name__, request.method, request.path]
                if vary_on_user:
                    parts.append(str(getattr(request.user, 'pk', 'anon')))
                if request.GET:
                    parts.append(request.GET.urlencode())
                cache_key = 'view_cache_' + hashlib.md5('|'.join(parts).encode()).hexdigest()

            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

            response = func(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response.data, timeout=ttl)
            return response
        return wrapper
    return decorator


def log_task_action(action: str = None):
    """
    Log task-related view actions for audit trail.

    Usage:
        @log_task_action('bulk_activate')
        def bulk_activate(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            user_id = getattr(request.user, 'pk', None)
            ip      = request.META.get('REMOTE_ADDR', '')
            act     = action or func.__name__
            logger.info(f"[TASK ACTION] user={user_id} action={act} ip={ip} path={request.path}")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE METHOD DECORATORS
# ══════════════════════════════════════════════════════════════════════════════

def retry_on_db_error(max_retries: int = 3, delay: float = 0.1):
    """
    Retry a service method on database transient errors.

    Usage:
        @retry_on_db_error(max_retries=3)
        def credit_wallet(user_id, amount): ...
    """
    from django.db import OperationalError, InterfaceError
    import time as _time

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, InterfaceError) as exc:
                    last_exc = exc
                    logger.warning(
                        f"[DB RETRY] {func.__name__} attempt {attempt}/{max_retries}: {exc}"
                    )
                    if attempt < max_retries:
                        _time.sleep(delay * attempt)
            raise last_exc
        return wrapper
    return decorator


def sync_to_data_bridge(namespace: str, field: str, ttl: int = 3600):
    """
    After a service method succeeds, sync the return value to DataBridge.

    Usage:
        @sync_to_data_bridge('user', 'wallet_balance', ttl=300)
        def get_wallet_balance(user_id): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                from api.tasks.integration.data_bridge import DataBridge
                # Try to infer entity_id from first argument
                entity_id = args[0] if args else kwargs.get('user_id') or kwargs.get('id')
                if entity_id is not None:
                    DataBridge.set(f"{namespace}:{entity_id}:{field}", result, ttl=ttl)
            except Exception as e:
                logger.debug(f"[DATA BRIDGE SYNC] {namespace}.{field}: {e}")
            return result
        return wrapper
    return decorator


__all__ = [
    'task_with_circuit_breaker', 'task_idempotent', 'task_with_lock',
    'task_timed', 'task_emit_event',
    'require_task_permission', 'require_verified_email', 'require_kyc',
    'rate_limit_task_action', 'cache_response', 'log_task_action',
    'retry_on_db_error', 'sync_to_data_bridge',
]

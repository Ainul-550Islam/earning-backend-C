# =============================================================================
# fraud_detection/decorators.py
#
# Decorators used across fraud detection views and services.
# =============================================================================
from __future__ import annotations

import functools
import logging
from typing import Callable

from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('fraud_detection.audit')


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------

def audit_log(action: str, log_request_data: bool = False):
    """
    Decorator for ViewSet action methods that writes a structured audit entry
    whenever the action is called.

    Usage::

        @audit_log(action='resolve_case')
        def resolve(self, request, *args, **kwargs):
            ...

    The decorator:
      1. Records *who* called *what* and *when* (before the action runs).
      2. On success, records the HTTP status of the response.
      3. On exception, logs the error and re-raises.
      4. Stores the audit entry in the DB (via IntegrationAuditLog if available,
         otherwise via Python logging only — so startup never fails if the model
         isn't migrated yet).

    Parameters
    ----------
    action : str
        A short snake_case identifier for the action, e.g. ``'resolve_case'``.
    log_request_data : bool
        If True, the request body is included in the audit entry (default False
        to avoid accidentally logging sensitive fields).
    """
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(view_self, request, *args, **kwargs):
            user_id   = request.user.pk if request.user.is_authenticated else None
            ip_addr   = _get_ip(request)
            started   = timezone.now()

            # ── Pre-call log ────────────────────────────────────────────────
            logger.info(
                'AUDIT_START action=%s user=%s ip=%s path=%s',
                action, user_id, ip_addr, request.path,
            )

            try:
                response = method(view_self, request, *args, **kwargs)
            except Exception as exc:
                logger.error(
                    'AUDIT_ERROR action=%s user=%s ip=%s error=%s',
                    action, user_id, ip_addr, exc,
                    exc_info=True,
                )
                raise

            ended       = timezone.now()
            duration_ms = int((ended - started).total_seconds() * 1000)
            http_status = getattr(response, 'status_code', None)

            # ── Post-call log ───────────────────────────────────────────────
            logger.info(
                'AUDIT_END action=%s user=%s ip=%s status=%s duration_ms=%s',
                action, user_id, ip_addr, http_status, duration_ms,
            )

            # ── Persist to DB (best-effort, never blocks response) ──────────
            _persist_audit(
                action       = action,
                user_id      = user_id,
                ip_address   = ip_addr,
                path         = request.path,
                http_method  = request.method,
                http_status  = http_status,
                started_at   = started,
                ended_at     = ended,
                duration_ms  = duration_ms,
                request_data = dict(request.data) if log_request_data else {},
            )

            return response

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# fraud_rate_limit
# ---------------------------------------------------------------------------

def fraud_rate_limit(max_attempts: int = 5, window_seconds: int = 60):
    """
    Lightweight rate-limiter for fraud-sensitive endpoints.

    Uses Django's cache backend (key = ``fraud:rl:{ip}:{view}:{action}``).
    Returns HTTP 429 if the limit is exceeded.

    Usage::

        @fraud_rate_limit(max_attempts=3, window_seconds=300)
        def sensitive_action(self, request, *args, **kwargs):
            ...
    """
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(view_self, request, *args, **kwargs):
            from django.core.cache import cache

            ip      = _get_ip(request)
            view_n  = type(view_self).__name__
            key     = f'fraud:rl:{ip}:{view_n}:{method.__name__}'

            count   = cache.get(key, 0)
            if count >= max_attempts:
                logger.warning(
                    'RATE_LIMIT_EXCEEDED ip=%s view=%s action=%s',
                    ip, view_n, method.__name__,
                )
                return Response(
                    {'detail': 'Too many requests. Please try again later.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            cache.set(key, count + 1, window_seconds)
            return method(view_self, request, *args, **kwargs)

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _persist_audit(**kwargs) -> None:
    """Write an audit record to the DB — silently swallows all errors."""
    try:
        from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import (
            get_audit_logger,
        )
        audit_logger = get_audit_logger()
        audit_logger.log_action(**kwargs)
    except Exception as exc:
        logger.debug('_persist_audit skipped: %s', exc)

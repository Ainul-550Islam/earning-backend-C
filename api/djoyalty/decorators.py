# api/djoyalty/decorators.py
"""
Djoyalty Decorators -- Reusable view/function decorators।
audit_action, require_loyalty_active, cache_loyalty_response, etc.
"""
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


def audit_action(action: str, category: str = 'api'):
    """Decorator: log action to AdminAuditLog after execution।"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                from .models.audit import AdminAuditLog
                # Try to get customer from result or kwargs
                customer = kwargs.get('customer')
                AdminAuditLog.log(
                    action=action,
                    category=category,
                    customer=customer,
                    performed_by='api',
                    description=f'{action} called',
                )
            except Exception:
                pass
            return result
        return wrapper
    return decorator


def require_loyalty_active(func):
    """Decorator: ensure loyalty system is active for tenant।"""
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if tenant and not tenant.is_active:
            from rest_framework.response import Response
            return Response({'error': 'Loyalty program is not active.'}, status=403)
        return func(self, request, *args, **kwargs)
    return wrapper


def cache_loyalty_response(timeout: int = 60, key_prefix: str = 'loyalty'):
    """Decorator: cache view response in Redis।"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            from django.core.cache import cache
            customer_id = request.query_params.get('customer_id', 'anon')
            cache_key = f'djoyalty:{key_prefix}:{func.__name__}:{customer_id}'
            cached = cache.get(cache_key)
            if cached is not None:
                from rest_framework.response import Response
                return Response(cached)
            response = func(self, request, *args, **kwargs)
            if hasattr(response, 'data') and response.status_code == 200:
                cache.set(cache_key, response.data, timeout=timeout)
            return response
        return wrapper
    return decorator


def rate_limit_customer(max_calls: int = 10, window: int = 60):
    """Decorator: rate limit by customer_id।"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            from django.core.cache import cache
            from rest_framework.response import Response
            customer_id = request.data.get('customer_id') or request.query_params.get('customer_id', 'anon')
            key = f'djoyalty:rl:{func.__name__}:{customer_id}'
            count = cache.get(key, 0)
            if count >= max_calls:
                return Response({'error': 'Rate limit exceeded.'}, status=429)
            cache.set(key, count + 1, timeout=window)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def track_performance(integration_name: str = ''):
    """Decorator: track function performance via PerformanceMonitor।"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            success = True
            error = ''
            try:
                return func(*args, **kwargs)
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = (time.monotonic() - start) * 1000
                try:
                    from .integration_system.performance_monitor import PerformanceMonitor
                    PerformanceMonitor._record(
                        integration=integration_name or func.__module__,
                        operation=func.__name__,
                        duration_ms=duration_ms,
                        success=success,
                        error=error,
                    )
                except Exception:
                    pass
        return wrapper
    return decorator


def validate_request_data(*required_fields):
    """Decorator: validate required fields in request.data।"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            from rest_framework.response import Response
            missing = [f for f in required_fields if not request.data.get(f)]
            if missing:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing)}'},
                    status=400,
                )
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator

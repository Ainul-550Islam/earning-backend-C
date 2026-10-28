"""
Function decorators for Telemetry Observability.

Wire into: services/, views/, viewsets/ — any function where you want
automatic metric recording, tracing, logging, caching, or alerting.

Usage:
    from .decorators import record_metric, trace_operation, measure_time

    @trace_operation(service='alert-service')
    @measure_time('alert_create_duration_ms')
    def create_alert(self, data):
        ...
"""
import time
from functools import wraps
from typing import Callable, Optional, Dict, Any

from .metrics import MetricsCollector
from .tracing import TracingService
# DRY FIX: was `from .logging import LoggingService` — no such module exists.
# LogEntry.objects.create() is the direct path; no extra logging.py needed.
from .models.log_entry import LogEntry
from .models.health_status import HealthStatus


# ---------------------------------------------------------------------------
# @record_metric
# ---------------------------------------------------------------------------

def record_metric(
    metric_name: str,
    metric_type: str = 'counter',
    unit: str = '',
    labels: Optional[Dict[str, Any]] = None,
    service: str = 'application',
    environment: str = 'production',
):
    """
    Decorator — records a metric on every function call.

    On success : records metric_name (counter) or execution duration (gauge).
    On failure : records metric_name_error counter with error label.

    Args:
        metric_name:  Metric name to record
        metric_type:  'counter' | 'gauge'. Gauge records call duration.
        unit:         Unit string (e.g. 'ms', 'count')
        labels:       Extra label dict merged onto every metric
        service:      Service tag
        environment:  Environment tag
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector   = MetricsCollector()
            start_time  = time.time()
            extra_labels = labels or {}

            try:
                result   = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000  # ms

                if metric_type == 'gauge':
                    collector.record_gauge(
                        name=metric_name, value=duration,
                        unit=unit or 'ms', labels=extra_labels,
                        service=service, environment=environment,
                    )
                else:
                    collector.record_counter(
                        name=metric_name, value=1,
                        unit=unit, labels=extra_labels,
                        service=service, environment=environment,
                    )
                return result

            except Exception as exc:
                collector.record_counter(
                    name=f'{metric_name}_error',
                    value=1,
                    unit=unit,
                    labels={**extra_labels, 'error': type(exc).__name__},
                    service=service,
                    environment=environment,
                )
                raise

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @trace_operation
# ---------------------------------------------------------------------------

def trace_operation(service: str = 'default', operation_name: Optional[str] = None):
    """
    Decorator — wraps a function in a distributed trace span.

    On success : span status = 'success'.
    On failure : span status = 'error', error is logged in span logs.

    Args:
        service:        Service name tag on the span
        operation_name: Override span name (defaults to function.__name__)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracing  = TracingService()
            op_name  = operation_name or func.__name__
            span     = tracing.start_span(operation_name=op_name, service=service)

            try:
                result = func(*args, **kwargs)
                tracing.finish_span(span.span_id, status='success')
                return result

            except Exception as exc:
                tracing.finish_span(
                    span.span_id,
                    status='error',
                    logs=[{'error': type(exc).__name__, 'message': str(exc)}],
                )
                raise

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @log_function_call
# ---------------------------------------------------------------------------

def log_function_call(
    level: str = 'info',
    include_args: bool = False,
    include_result: bool = False,
    service: str = 'application',
    environment: str = 'production',
):
    """
    Decorator — logs entry and exit of a function.

    DRY FIX: uses LogEntry.objects.create() directly — no separate LoggingService needed.

    Args:
        level:          Log level for entry/exit messages
        include_args:   Attach args/kwargs in context
        include_result: Attach return value in context (use with care for large objects)
        service:        Service tag on the log
        environment:    Environment tag
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            context: Dict[str, Any] = {
                'function': func.__name__,
                'module':   func.__module__,
            }
            if include_args:
                context['args']   = repr(args)
                context['kwargs'] = repr(kwargs)

            LogEntry.objects.create(
                level=level,
                message=f'Calling {func.__qualname__}',
                logger_name=func.__module__,
                source='decorator',
                service=service,
                environment=environment,
                context=context,
            )

            try:
                result = func(*args, **kwargs)

                if include_result:
                    context['result'] = repr(result)
                    LogEntry.objects.create(
                        level=level,
                        message=f'{func.__qualname__} completed',
                        logger_name=func.__module__,
                        source='decorator',
                        service=service,
                        environment=environment,
                        context=context,
                    )
                return result

            except Exception as exc:
                LogEntry.objects.create(
                    level='error',
                    message=f'{func.__qualname__} failed: {exc}',
                    logger_name=func.__module__,
                    source='decorator',
                    service=service,
                    environment=environment,
                    context={**context, 'error': str(exc)},
                )
                raise

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @measure_time
# ---------------------------------------------------------------------------

def measure_time(metric_name: Optional[str] = None, service: str = 'application'):
    """
    Decorator — records function execution time as a gauge metric (ms).

    Args:
        metric_name: Metric name (defaults to '<function_name>_duration_ms')
        service:     Service tag
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name      = metric_name or f'{func.__name__}_duration_ms'
            start     = time.time()
            result    = func(*args, **kwargs)
            duration  = (time.time() - start) * 1000

            MetricsCollector().record_gauge(
                name=name, value=duration, unit='ms', service=service
            )
            return result

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @alert_on_failure
# ---------------------------------------------------------------------------

def alert_on_failure(
    alert_name: str,
    severity: str = 'warning',
    message: Optional[str] = None,
    service: str = 'application',
):
    """
    Decorator — creates an alert when the decorated function raises an exception.

    Args:
        alert_name: Alert name
        severity:   Alert severity
        message:    Custom message (defaults to error description)
        service:    Service tag
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                from .alerting import AlertingService
                alert_msg = message or f'{func.__qualname__} failed: {exc}'
                AlertingService().create_alert(
                    name=alert_name,
                    alert_type='custom',
                    severity=severity,
                    message=alert_msg,
                    condition={'function': func.__qualname__, 'error': str(exc)},
                    service=service,
                )
                raise

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @health_check
# ---------------------------------------------------------------------------

def health_check(service_name: str, environment: str = 'production'):
    """
    Decorator — marks a function as a health-check probe.

    On success : updates HealthStatus to healthy / score 100.
    On failure : updates HealthStatus to unhealthy / score 0.

    Args:
        service_name: Service name for the HealthStatus record
        environment:  Environment tag
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            defaults_healthy   = {'status': 'healthy',   'health_score': 100, 'environment': environment}
            defaults_unhealthy = {'status': 'unhealthy', 'health_score': 0,   'environment': environment}

            try:
                result = func(*args, **kwargs)
                HealthStatus.objects.update_or_create(
                    service_name=service_name,
                    defaults=defaults_healthy,
                )
                return result

            except Exception:
                HealthStatus.objects.update_or_create(
                    service_name=service_name,
                    defaults=defaults_unhealthy,
                )
                raise

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @cache_result
# ---------------------------------------------------------------------------

def cache_result(ttl: int = 60):
    """
    Decorator — caches function return value in Django's cache backend.

    Args:
        ttl: Time-to-live in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from django.core.cache import cache
            cache_key    = f'{func.__module__}.{func.__qualname__}:{args}:{kwargs}'
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# @retry_on_failure
# ---------------------------------------------------------------------------

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator — retries the function on any exception.

    Args:
        max_retries: Maximum number of attempts
        delay:       Seconds to wait between retries
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            raise last_exc

        return wrapper
    return decorator

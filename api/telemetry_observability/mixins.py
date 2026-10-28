"""
Reusable view/viewset mixins for Telemetry Observability.

WIRING — inherit in viewsets:
    class MetricViewSet(TelemetryMixin, MetricMixin, ResponseMixin,
                        CacheMixin, viewsets.ModelViewSet):
        ...

DRY: All request-level telemetry logic lives here.
     Views NEVER re-implement get_client_ip(), log_event(), etc.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from rest_framework.response import Response


# ---------------------------------------------------------------------------
# TelemetryMixin — base: extracts request metadata
# ---------------------------------------------------------------------------

class TelemetryMixin:
    """
    Base mixin — provides telemetry context from the current request.
    All other mixins inherit from this.
    """

    def get_telemetry_context(self) -> Dict[str, Any]:
        """
        Return a dict of request-level telemetry metadata.
        Used as base context for metrics, logs, traces.
        """
        request = self.request
        return {
            'method':     request.method,
            'path':       request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self._get_client_ip(request),
            'user_id':    getattr(request.user, 'id', None),
        }

    @staticmethod
    def _get_client_ip(request) -> str:
        """Return the real client IP, honouring X-Forwarded-For."""
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


# ---------------------------------------------------------------------------
# MetricMixin — records a counter/gauge per view invocation
# ---------------------------------------------------------------------------

class MetricMixin(TelemetryMixin):
    """
    Mixin — call self.record_metric() inside any view action to emit a metric.
    DRY: never import MetricsCollector directly inside a view — call this instead.
    """

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: str = 'counter',
        **kwargs,
    ) -> None:
        """
        Record a metric from a view.

        Args:
            name:        Metric name
            value:       Metric value
            metric_type: 'counter' | 'gauge' | 'histogram' | 'summary'
            **kwargs:    unit, labels, source, service, environment
        """
        from .metrics import MetricsCollector
        collector = MetricsCollector()
        context   = self.get_telemetry_context()
        labels    = {**kwargs.get('labels', {}), **context}

        record_method = {
            'counter':   collector.record_counter,
            'gauge':     collector.record_gauge,
            'histogram': collector.record_histogram,
            'summary':   collector.record_summary,
        }.get(metric_type, collector.record_counter)

        record_method(
            name=name,
            value=value,
            unit=kwargs.get('unit', ''),
            labels=labels,
            source=kwargs.get('source', 'view'),
            service=kwargs.get('service', 'django_app'),
            environment=kwargs.get('environment', 'production'),
        )


# ---------------------------------------------------------------------------
# LoggingMixin — creates a LogEntry from a view
# ---------------------------------------------------------------------------

class LoggingMixin(TelemetryMixin):
    """
    Mixin — call self.log_event() to emit a log entry from a view.
    DRY: never import LogEntry directly inside a view — call this instead.
    """

    def log_event(self, level: str, message: str, **kwargs) -> None:
        """
        Create a log entry from a view action.

        Args:
            level:   'debug' | 'info' | 'warning' | 'error' | 'critical'
            message: Log message
            **kwargs: logger_name, source, service, environment, context, tags
        """
        from .models.log_entry import LogEntry
        context = {**self.get_telemetry_context(), **kwargs.get('context', {})}
        LogEntry.objects.create(
            level=level,
            message=message,
            logger_name=kwargs.get('logger_name', 'view'),
            source=kwargs.get('source', 'view'),
            service=kwargs.get('service', 'django_app'),
            environment=kwargs.get('environment', 'production'),
            context=context,
            tags=kwargs.get('tags', []),
        )


# ---------------------------------------------------------------------------
# TracingMixin — starts/finishes a span from a view
# ---------------------------------------------------------------------------

class TracingMixin(TelemetryMixin):
    """
    Mixin — call self.start_trace() / self.finish_trace() to add distributed
    tracing to a view action.
    """

    def start_trace(self, operation_name: str, **kwargs):
        """Start a trace span. Returns the TraceSpan instance."""
        from .tracing import TracingService
        tags = {**self.get_telemetry_context(), **kwargs.get('tags', {})}
        return TracingService().start_span(
            operation_name=operation_name,
            service=kwargs.get('service', 'django_app'),
            tags=tags,
        )

    def finish_trace(self, span_id: str, status: str = 'success', **kwargs) -> None:
        """Finish a trace span by its span_id."""
        from .tracing import TracingService
        TracingService().finish_span(
            span_id=span_id,
            status=status,
            logs=kwargs.get('logs', []),
            context=kwargs.get('context', {}),
        )


# ---------------------------------------------------------------------------
# AlertingMixin — creates alerts from a view
# ---------------------------------------------------------------------------

class AlertingMixin(TelemetryMixin):
    """
    Mixin — call self.create_alert() to trigger an alert from a view.
    """

    def create_alert(self, name: str, severity: str, message: str, **kwargs) -> None:
        """Create an alert. Delegates to AlertingService (no logic duplicated here)."""
        from .alerting import AlertingService
        condition = {**self.get_telemetry_context(), **kwargs.get('condition', {})}
        AlertingService().create_alert(
            name=name,
            alert_type=kwargs.get('alert_type', 'custom'),
            severity=severity,
            message=message,
            condition=condition,
            source=kwargs.get('source', 'view'),
            service=kwargs.get('service', 'django_app'),
            environment=kwargs.get('environment', 'production'),
            metadata=kwargs.get('metadata', {}),
        )


# ---------------------------------------------------------------------------
# ResponseMixin — standardised envelope responses
# ---------------------------------------------------------------------------

class ResponseMixin:
    """
    Mixin — provides success_response() and error_response() helpers so
    every viewset returns the same JSON envelope without repeating the dict.

    DRY: no viewset constructs {'success': True, ...} by hand.
    """

    def success_response(
        self,
        data: Any = None,
        message: Optional[str] = None,
        status_code: int = 200,
    ) -> Response:
        return Response(
            {'success': True, 'message': message, 'data': data},
            status=status_code,
        )

    def error_response(
        self,
        message: str,
        errors: Optional[list] = None,
        status_code: int = 400,
    ) -> Response:
        return Response(
            {'success': False, 'message': message, 'errors': errors or []},
            status=status_code,
        )


# ---------------------------------------------------------------------------
# PerformanceMixin — context manager for inline timing
# ---------------------------------------------------------------------------

class PerformanceMixin:
    """
    Mixin — provides a context manager for timing a code block.

    Usage in a viewset:
        with self.track_performance('create_metric'):
            metric = service.collect_metric(data)
    """

    def track_performance(self, operation: str = 'operation'):
        """Return a context manager that records execution time."""

        outer_self = self

        class _Tracker:
            def __enter__(self_):
                self_._start = time.perf_counter()
                return self_

            def __exit__(self_, exc_type, exc_val, exc_tb):
                duration_ms = (time.perf_counter() - self_._start) * 1000
                if hasattr(outer_self, 'record_metric'):
                    outer_self.record_metric(
                        name=f'{operation}_duration_ms',
                        value=duration_ms,
                        metric_type='gauge',
                        unit='ms',
                    )
                return False  # do not suppress exceptions

        return _Tracker()


# ---------------------------------------------------------------------------
# CacheMixin — simple Django cache wrapper for views
# ---------------------------------------------------------------------------

class CacheMixin:
    """
    Mixin — provides get_cached() / set_cached() so views use cache
    without importing django.core.cache directly.

    DRY: all cache logic in one place; change eviction policy here only.
    """

    def get_cached(self, key: str) -> Optional[Any]:
        from django.core.cache import cache
        return cache.get(key)

    def set_cached(self, key: str, data: Any, timeout: int = 300) -> None:
        from django.core.cache import cache
        cache.set(key, data, timeout)

    def delete_cached(self, key: str) -> None:
        from django.core.cache import cache
        cache.delete(key)


# ---------------------------------------------------------------------------
# FilterMixin — applies a dict of filters to a queryset
# ---------------------------------------------------------------------------

class FilterMixin:
    """
    Mixin — call self.apply_filters(queryset, filters_dict) to apply
    arbitrary field filters without repeating filter logic in every viewset.
    """

    def apply_filters(self, queryset, filters: Dict[str, Any]):
        """
        Apply key=value filters to queryset, skipping None values.
        Supports lookup suffixes: __gte, __lte, __icontains, etc.
        """
        for key, value in filters.items():
            if value is not None:
                queryset = queryset.filter(**{key: value})
        return queryset

    def apply_sorting(self, queryset, sort_by: Optional[str], order: str = 'asc'):
        """Apply ordering. order='desc' prepends '-'."""
        if sort_by:
            prefix = '' if order == 'asc' else '-'
            queryset = queryset.order_by(f'{prefix}{sort_by}')
        return queryset

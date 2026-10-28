"""
Request-level middleware for Telemetry Observability.

ADD TO settings.py MIDDLEWARE LIST (order matters — place early):

    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        'telemetry_observability.middleware.TelemetryMiddleware',  # ← add here
        'django.contrib.sessions.middleware.SessionMiddleware',
        ...
    ]

DRY: All request-level metric/trace/log recording lives here.
     Views NEVER manually record request_count, request_duration etc.
"""
import logging
import time

logger = logging.getLogger(__name__)


class TelemetryMiddleware:
    """
    WSGI/ASGI middleware that auto-records metrics, logs, and traces
    for every HTTP request passing through Django.

    Captures:
      - Metric  : http_request_total (counter) per method+path+status
      - Metric  : http_request_duration_ms (gauge) per request
      - Log     : ERROR-level log for 5xx responses
      - Trace   : one span per request (start on enter, finish on exit)

    All writes are lazy-imported to survive being loaded before the
    Django app registry is fully ready.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.perf_counter()

        # --- start trace span ---
        span = self._start_span(request)

        # --- execute view ---
        response = self.get_response(request)

        # --- compute duration ---
        duration_ms = (time.perf_counter() - start_time) * 1000

        # --- record metrics ---
        self._record_request_metric(request, response, duration_ms)

        # --- finish trace span ---
        self._finish_span(span, response, duration_ms)

        # --- log 5xx errors ---
        if response.status_code >= 500:
            self._log_server_error(request, response, duration_ms)

        return response

    # ------------------------------------------------------------------

    def _start_span(self, request):
        """Start a distributed trace span for the incoming request."""
        try:
            from .tracing import TracingService
            return TracingService().start_span(
                operation_name=f'{request.method} {request.path}',
                service='django_http',
                tags={
                    'http.method': request.method,
                    'http.url':    request.build_absolute_uri(),
                    'http.path':   request.path,
                },
            )
        except Exception:
            return None

    def _finish_span(self, span, response, duration_ms: float) -> None:
        """Finish the trace span with the final HTTP status."""
        if span is None:
            return
        try:
            from .tracing import TracingService
            status = 'error' if response.status_code >= 400 else 'success'
            TracingService().finish_span(
                span_id=span.span_id,
                status=status,
                context={'http.status_code': response.status_code,
                         'duration_ms': round(duration_ms, 2)},
            )
        except Exception:
            pass

    def _record_request_metric(self, request, response, duration_ms: float) -> None:
        """Record per-request counter and duration gauge."""
        try:
            from .metrics import MetricsCollector
            collector = MetricsCollector()
            labels = {
                'method':      request.method,
                'path':        request.path,
                'status_code': str(response.status_code),
            }
            collector.record_counter(
                name='http_request_total',
                value=1,
                labels=labels,
                service='django_http',
            )
            collector.record_gauge(
                name='http_request_duration_ms',
                value=round(duration_ms, 2),
                unit='ms',
                labels=labels,
                service='django_http',
            )
        except Exception:
            pass

    def _log_server_error(self, request, response, duration_ms: float) -> None:
        """Write an error-level LogEntry for every 5xx response."""
        try:
            from .models.log_entry import LogEntry
            LogEntry.objects.create(
                level='error',
                message=(
                    f'HTTP {response.status_code} on '
                    f'{request.method} {request.path}'
                ),
                logger_name='telemetry.middleware',
                source='middleware',
                service='django_http',
                context={
                    'method':      request.method,
                    'path':        request.path,
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'user_id':     getattr(request.user, 'id', None),
                },
            )
        except Exception:
            pass

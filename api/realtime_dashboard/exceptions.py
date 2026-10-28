"""
Custom exceptions and DRF exception handler for Real-time Dashboard Backend.
"""
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status


# ── Custom application exceptions ────────────────────────────────────────────

class DashboardException(Exception):
    """Base exception for all dashboard-related errors."""
    pass


class WidgetNotFoundError(DashboardException):
    """Raised when a DashboardWidget cannot be found."""
    pass


class MetricNotFoundError(DashboardException):
    """
    Raised when a RealTimeMetric cannot be found.

    Wired: RealTimeMetricService.get_metric_or_raise() raises this (see
    services/real_time_metric_service.py). That method itself has no
    caller — investigated three candidate call sites, v9 audit:

      - RealTimeMetricViewSet.activate/deactivate/retrieve/update/destroy
        use DRF's own get_object(), which already 404s correctly on the
        URL's own pk. Routing get_metric_or_raise() through here too
        would be a second, redundant lookup.
      - RealTimeMetricViewSet.aggregate() takes a list of metric_ids and
        intentionally tolerates missing ones (composite/average metrics
        across servers, regions, etc. — a partial match is a valid
        result, not an error). Raising on the first missing id would
        change working, deliberate behavior.
      - MetricConsumer.connect() (WebSocket) was the most plausible
        candidate — validate metric_id before subscribing, instead of
        silently joining a group that will never receive a broadcast.
        Rejected: test_metric_consumer_authenticated_connect,
        _ping_pong, _broadcast, and _authenticated_disconnect all
        connect to metric ids with no backing RealTimeMetric row —
        metric_id is exercised, in the test suite as it stands today, as
        a bare pub/sub topic name, not a resource reference. Adding
        existence validation would break four passing tests encoding
        that choice, not fix a bug. Flagging this as a real product
        question worth a deliberate answer — should connecting to a
        not-yet-existent metric be allowed (current behavior) or
        rejected (needs get_metric_or_raise() wired here, and those four
        tests rewritten to create a metric first) — rather than picking
        one silently.

    Left as documented-available, same status as get_metric() itself.
    """
    pass


class DashboardNotFoundError(DashboardException):
    """Raised when a UserDashboard cannot be found."""
    pass


class WebSocketConnectionError(DashboardException):
    """
    Raised when a WebSocket connection operation fails.

    Investigated four candidate call sites, v9 audit — none fit without
    inventing a failure mode that doesn't currently exist or changing
    tested behavior:

      - WebSocketManager._send_to_connection() / the public
        broadcast_to_connection() wrapper: could validate the target
        connection_id against a live WebSocketConnection row before
        sending. Rejected: test_send_to_connection (test_websocket_
        manager.py) and test_send_to_connection_returns_true_when_no_
        layer (test_coverage_gaps.py) both send to connection ids with
        no backing row and assert True — fire-and-forget delivery to a
        channel name nobody's listening on is the documented, tested
        contract (see _send_to_connection's own docstring), not a gap.
      - WebSocketManagerService.record_ping()/remove_connection() return
        bool rather than raising on "no matching connected row". Their
        one caller (base_consumer.py's track_ping/track_disconnect)
        already treats a stale/unmatched ping as benign (client's socket
        is still open; only our bookkeeping aged it out) — raising here
        would mean closing a functioning connection over a harmless
        race, which is a worse outcome than the current no-op.
      - signals.py's dashboard_updated() already wraps
        EventStreamingService().stream_dashboard_updates() in a broad
        except Exception (broadcast failures must never roll back a
        save()) — anything raised here gets caught and logged, not
        surfaced as a distinct error type; narrowing that catch to
        something WebSocketConnectionError-specific wouldn't change
        behavior, only the log line.
      - No consumer or service currently distinguishes "channel layer
        misconfigured" from "channel layer unreachable" from "target
        gone" — every current failure path already has a defined,
        tested outcome (safe no-op, or bool return) that predates this
        exception class.

    Left as documented-available. A real fit would be a new failure mode
    that doesn't have defined behavior yet, not a retrofit onto a path
    that already has one.
    """
    pass


class InvalidWidgetDataError(DashboardException):
    """
    Raised when widget data fails validation.

    Investigated the two "widget data" validation paths in the codebase,
    v9 audit — both are already correctly handled by DRF itself, and
    InvalidWidgetDataError would be a worse fit for either:

      - DashboardWidgetSerializer.configuration field: validated by
        validators.validate_widget_configuration(), which raises DRF's
        own serializers.ValidationError. That's the right exception here
        — it gives the client a structured per-field error
        ({"configuration": ["..."]}) via DRF's normal is_valid() flow.
        Swapping in InvalidWidgetDataError would trade a structured
        field error for a flat string one; strictly worse for API
        consumers, not a fix.
      - WidgetConfigurationSerializer.value field (a different model —
        key/value config entries, not the widget's own configuration
        blob): validated by utils.validate_widget_configuration()
        (bool-returning), which the serializer's validate_value() already
        wraps in its own serializers.ValidationError. Same reasoning.
      - No bulk/import-style widget endpoint exists (checked every
        @action across every viewset) where a list of widget dicts gets
        processed outside the normal single-object serializer flow —
        that would be the shape of endpoint where a non-DRF domain
        exception earns its keep instead of duplicating validators.py.

    Left as documented-available for that kind of endpoint, if one gets
    built — not force-fit onto paths DRF already validates correctly.
    """
    pass


class DashboardEngineError(DashboardException):
    """Raised when the DashboardEngine fails to render a dashboard or widget."""
    pass


# ── DRF exception handler ─────────────────────────────────────────────────────

# Map application exceptions to HTTP status codes.
_APP_EXCEPTION_STATUS_MAP = {
    WidgetNotFoundError: status.HTTP_404_NOT_FOUND,
    MetricNotFoundError: status.HTTP_404_NOT_FOUND,
    DashboardNotFoundError: status.HTTP_404_NOT_FOUND,
    DashboardEngineError: status.HTTP_404_NOT_FOUND,
    InvalidWidgetDataError: status.HTTP_400_BAD_REQUEST,
    WebSocketConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
    DashboardException: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that:
    1. Wraps every error response in the app's standard envelope
       {"success": false, "error": ..., "status_code": ...}  so clients
       always receive a predictable structure regardless of whether the
       error came from DRF validation, a 404 lookup, or an application
       exception.
    2. Converts app-specific exceptions (WidgetNotFoundError etc.) into
       proper HTTP responses instead of letting them bubble up as 500s.

    Register in settings.py:
        REST_FRAMEWORK = {
            'EXCEPTION_HANDLER':
                'api.realtime_dashboard.exceptions.custom_exception_handler',
        }
    """
    # Let DRF handle its own exceptions first (ValidationError, NotFound, etc.)
    response = drf_exception_handler(exc, context)

    if response is not None:
        # Normalise DRF's response into the app envelope.
        original_detail = response.data
        response.data = {
            'success': False,
            'error': original_detail,
            'status_code': response.status_code,
        }
        return response

    # Handle application-specific exceptions that DRF doesn't know about.
    for exc_class, http_status in _APP_EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_class):
            return Response(
                {
                    'success': False,
                    'error': str(exc),
                    'status_code': http_status,
                },
                status=http_status,
            )

    # Unknown exception - let Django's 500 handler deal with it.
    return None

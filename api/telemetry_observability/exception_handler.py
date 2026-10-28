"""
Custom DRF exception handler for Telemetry Observability.

Wired in settings/base.py:
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'telemetry_observability.exception_handler.telemetry_exception_handler'
    }

DRY: every error response has the same shape — defined ONCE here.
     No view catches exceptions manually unless it needs custom recovery logic.

Error envelope:
  {
    "success": false,
    "data":    null,
    "error": {
      "code":    "VALIDATION_ERROR",
      "message": "Human-readable description",
      "detail":  <drf_detail_object>,
      "fields":  {"field_name": ["error msg"]}  ← for 400s
    },
    "meta": { ... }   ← added by TelemetryJSONRenderer
  }
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler
from rest_framework.exceptions import (
    ValidationError, AuthenticationFailed, NotAuthenticated,
    PermissionDenied, NotFound, MethodNotAllowed, Throttled,
    ParseError, UnsupportedMediaType,
)

from .exceptions import (
    TelemetryException, MetricException, LogException,
    TraceException, AlertException, HealthCheckException, DashboardException,
)

logger = logging.getLogger(__name__)


# ── Error code mapping ────────────────────────────────────────────────────────

_DRF_CODE_MAP = {
    ValidationError:       'VALIDATION_ERROR',
    AuthenticationFailed:  'AUTHENTICATION_FAILED',
    NotAuthenticated:      'NOT_AUTHENTICATED',
    PermissionDenied:      'PERMISSION_DENIED',
    NotFound:              'NOT_FOUND',
    MethodNotAllowed:      'METHOD_NOT_ALLOWED',
    Throttled:             'RATE_LIMIT_EXCEEDED',
    ParseError:            'PARSE_ERROR',
    UnsupportedMediaType:  'UNSUPPORTED_MEDIA_TYPE',
}

_TELEMETRY_CODE_MAP = {
    MetricException:       'METRIC_ERROR',
    LogException:          'LOG_ERROR',
    TraceException:        'TRACE_ERROR',
    AlertException:        'ALERT_ERROR',
    HealthCheckException:  'HEALTH_CHECK_ERROR',
    DashboardException:    'DASHBOARD_ERROR',
    TelemetryException:    'TELEMETRY_ERROR',
}


def _extract_fields(detail):
    """
    Pull field-level errors from a DRF ValidationError detail dict.
    Returns a dict of {field: [messages]} or None.
    """
    if not isinstance(detail, dict):
        return None
    fields = {}
    for key, value in detail.items():
        if isinstance(value, list):
            fields[key] = [str(v) for v in value]
        else:
            fields[key] = [str(value)]
    return fields or None


def telemetry_exception_handler(exc, context):
    """
    Global exception handler.
    Converts ALL exceptions to the standard telemetry error envelope.
    """
    request = context.get('request')
    view    = context.get('view')

    # ── 1. Let DRF handle its own exceptions first ────────────────────────────
    response = drf_default_handler(exc, context)

    if response is not None:
        # DRF handled it — reformat to our envelope
        exc_type = type(exc)
        code     = _DRF_CODE_MAP.get(exc_type, 'API_ERROR')
        detail   = response.data

        error_body = {
            'code':    code,
            'message': _human_message(exc, code),
            'detail':  detail,
            'fields':  _extract_fields(detail) if isinstance(exc, ValidationError) else None,
        }
        response.data = {'success': False, 'data': None, 'error': error_body}
        return response

    # ── 2. Domain exceptions (TelemetryException subclasses) ─────────────────
    if isinstance(exc, TelemetryException):
        exc_type = type(exc)
        code     = getattr(exc, 'code', None) or _TELEMETRY_CODE_MAP.get(
            exc_type, 'TELEMETRY_ERROR'
        )
        logger.warning('TelemetryException [%s]: %s', code, exc.message)
        return Response(
            {
                'success': False,
                'data':    None,
                'error':   {
                    'code':    code,
                    'message': exc.message,
                    'detail':  str(exc),
                    'fields':  None,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── 3. Unhandled exceptions → 500 ────────────────────────────────────────
    logger.exception(
        'Unhandled exception in %s: %s',
        getattr(view, '__class__', {__name__: 'unknown'}).__name__,
        exc,
    )
    return Response(
        {
            'success': False,
            'data':    None,
            'error':   {
                'code':    'INTERNAL_SERVER_ERROR',
                'message': 'An unexpected error occurred. Please try again later.',
                'detail':  None,
                'fields':  None,
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _human_message(exc, code: str) -> str:
    """Return a user-friendly message for common DRF exceptions."""
    messages = {
        'VALIDATION_ERROR':      'The request data is invalid.',
        'AUTHENTICATION_FAILED': 'Authentication credentials are invalid.',
        'NOT_AUTHENTICATED':     'Authentication credentials were not provided.',
        'PERMISSION_DENIED':     'You do not have permission to perform this action.',
        'NOT_FOUND':             'The requested resource was not found.',
        'METHOD_NOT_ALLOWED':    'This HTTP method is not allowed.',
        'RATE_LIMIT_EXCEEDED':   'Too many requests. Please slow down.',
        'PARSE_ERROR':           'Request body could not be parsed.',
        'UNSUPPORTED_MEDIA_TYPE':'Unsupported content type.',
    }
    return messages.get(code, str(exc))

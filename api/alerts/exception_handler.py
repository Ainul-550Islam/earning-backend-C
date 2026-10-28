"""
alerts/exception_handler.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW FILE — Central DRF exception handler wiring exceptions.py.

Previously: exceptions.py defined 12 custom exception classes that
were NEVER referenced anywhere — zero API exposure.

Now: This handler converts all custom alerts exceptions into
structured DRF responses with correct HTTP status codes.

Register in settings:
    REST_FRAMEWORK = {
        'EXCEPTION_HANDLER': 'api.alerts.exception_handler.alerts_exception_handler',
    }
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from api.alerts.exceptions import (
    AlertSystemException,
    ValidationError as AlertValidationError,
    InvalidThresholdError,
    InvalidTimeWindowError,
    InvalidRecipientError,
    AlertProcessingError,
    AlertRuleNotFoundError,
    AlertRuleInactiveError,
)

logger = logging.getLogger(__name__)

# ── Exception → HTTP status mapping ──────────────────────────────
_STATUS_MAP = {
    AlertRuleNotFoundError:    status.HTTP_404_NOT_FOUND,
    AlertRuleInactiveError:    status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidThresholdError:     status.HTTP_400_BAD_REQUEST,
    InvalidTimeWindowError:    status.HTTP_400_BAD_REQUEST,
    InvalidRecipientError:     status.HTTP_400_BAD_REQUEST,
    AlertValidationError:      status.HTTP_400_BAD_REQUEST,
    AlertProcessingError:      status.HTTP_500_INTERNAL_SERVER_ERROR,
    AlertSystemException:      status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def alerts_exception_handler(exc, context):
    """
    Custom DRF exception handler.

    Handles all api.alerts.exceptions.* types and falls back to
    DRF's default handler for standard exceptions (AuthenticationFailed, etc.).
    """
    # Check alerts-specific exceptions first
    for exc_class, http_status in _STATUS_MAP.items():
        if isinstance(exc, exc_class):
            logger.warning(
                "Alerts exception [%s] in %s: %s",
                exc_class.__name__,
                _get_view_name(context),
                str(exc),
            )
            return Response(
                {
                    "error": exc_class.__name__,
                    "message": str(exc),
                    "code": getattr(exc, "code", exc_class.__name__.lower()),
                },
                status=http_status,
            )

    # Fall through to DRF's standard handler
    response = drf_exception_handler(exc, context)

    if response is not None:
        # Normalise DRF response shape to match our format
        if isinstance(response.data, dict) and "detail" in response.data:
            response.data = {
                "error": "APIError",
                "message": str(response.data["detail"]),
                "code": getattr(response.data.get("detail"), "code", "error"),
            }

    return response


def _get_view_name(context):
    view = context.get("view")
    if view is None:
        return "unknown"
    return f"{view.__class__.__module__}.{view.__class__.__name__}"

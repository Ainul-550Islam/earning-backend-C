"""
SmartLink Custom Exception Handler
Returns structured, consistent JSON error responses for every error type.
Includes request ID tracking, error codes, and developer-friendly messages.
"""
import logging
import traceback
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException, AuthenticationFailed, NotAuthenticated,
    PermissionDenied, NotFound, MethodNotAllowed, Throttled,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('smartlink.api.errors')


def custom_exception_handler(exc, context):
    """
    Central exception handler for all SmartLink API endpoints.
    Returns a consistent JSON structure:
    {
        "success": false,
        "error": {
            "code": "error_code",
            "message": "Human readable message",
            "detail": "...",
            "request_id": "uuid",
            "field_errors": {...}   // for validation errors
        }
    }
    """
    request = context.get('request')
    request_id = str(uuid.uuid4())[:8]

    # ── Handle Django ValidationError (convert to DRF) ───────────────
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(detail=exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)

    # ── Let DRF handle it first ───────────────────────────────────────
    response = drf_exception_handler(exc, context)

    if response is not None:
        error_payload = _build_error_payload(exc, response, request_id)
        log_level = _get_log_level(response.status_code)
        getattr(logger, log_level)(
            f"[{request_id}] {response.status_code} {_get_path(request)} "
            f"— {error_payload['error']['code']}: {error_payload['error']['message']}"
        )
        return Response(error_payload, status=response.status_code)

    # ── Unhandled exception (500) ─────────────────────────────────────
    logger.error(
        f"[{request_id}] Unhandled exception on {_get_path(request)}: {exc}",
        exc_info=True,
    )

    # Send to Sentry if configured
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass

    payload = {
        'success': False,
        'error': {
            'code': 'internal_server_error',
            'message': 'An unexpected error occurred. Our team has been notified.',
            'request_id': request_id,
        }
    }

    # In debug mode, include traceback
    if settings.DEBUG:
        payload['error']['traceback'] = traceback.format_exc()

    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _build_error_payload(exc, response, request_id: str) -> dict:
    """Build structured error payload from exception."""
    code    = _get_error_code(exc)
    message = _get_error_message(exc)
    detail  = response.data

    payload = {
        'success': False,
        'error': {
            'code':       code,
            'message':    message,
            'request_id': request_id,
            'status':     response.status_code,
        }
    }

    # Validation errors: include field-level errors
    if isinstance(exc, DRFValidationError):
        if isinstance(detail, dict):
            payload['error']['field_errors'] = _flatten_field_errors(detail)
        elif isinstance(detail, list):
            payload['error']['field_errors'] = {'non_field_errors': detail}
    else:
        if isinstance(detail, dict) and 'detail' in detail:
            payload['error']['detail'] = str(detail['detail'])
        elif isinstance(detail, str):
            payload['error']['detail'] = detail

    return payload


def _get_error_code(exc) -> str:
    """Map exception to error code string."""
    code_map = {
        NotAuthenticated:  'not_authenticated',
        AuthenticationFailed: 'authentication_failed',
        PermissionDenied:  'permission_denied',
        NotFound:          'not_found',
        Http404:           'not_found',
        MethodNotAllowed:  'method_not_allowed',
        Throttled:         'rate_limit_exceeded',
        DRFValidationError: 'validation_error',
    }
    for exc_class, code in code_map.items():
        if isinstance(exc, exc_class):
            return code

    # SmartLink custom exceptions
    if hasattr(exc, 'default_code'):
        return exc.default_code

    return 'api_error'


def _get_error_message(exc) -> str:
    """Get human-readable error message."""
    msg_map = {
        NotAuthenticated:   'Authentication required. Please provide a valid token.',
        AuthenticationFailed: 'Authentication failed. Invalid or expired credentials.',
        PermissionDenied:   'You do not have permission to perform this action.',
        NotFound:           'The requested resource was not found.',
        Http404:            'The requested resource was not found.',
        MethodNotAllowed:   'This HTTP method is not allowed on this endpoint.',
        Throttled:          'Too many requests. Please slow down.',
        DRFValidationError: 'Validation failed. Please check your input.',
    }
    for exc_class, msg in msg_map.items():
        if isinstance(exc, exc_class):
            return msg

    if hasattr(exc, 'default_detail'):
        return str(exc.default_detail)

    return str(exc) or 'An error occurred.'


def _flatten_field_errors(errors: dict, prefix: str = '') -> dict:
    """Flatten nested field error dicts into flat key→[messages] format."""
    flat = {}
    for field, error_list in errors.items():
        key = f"{prefix}.{field}" if prefix else field
        if isinstance(error_list, dict):
            flat.update(_flatten_field_errors(error_list, prefix=key))
        elif isinstance(error_list, list):
            flat[key] = [str(e) for e in error_list]
        else:
            flat[key] = [str(error_list)]
    return flat


def _get_log_level(status_code: int) -> str:
    if status_code >= 500:
        return 'error'
    if status_code >= 400:
        return 'warning'
    return 'info'


def _get_path(request) -> str:
    if request:
        return f"{request.method} {request.path}"
    return 'unknown'

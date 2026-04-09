# api/djoyalty/exception_handler.py
"""
Global DRF Exception Handler for Djoyalty।
settings.py এ যোগ করুন:
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'api.djoyalty.exception_handler.djoyalty_exception_handler',
}
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.db import IntegrityError

from .exceptions import DjoyaltyError

logger = logging.getLogger('djoyalty.exceptions')


def djoyalty_exception_handler(exc, context):
    """
    World-class exception handler:
    - DjoyaltyError → structured JSON with error code
    - DRF exceptions → standardized format
    - Django exceptions → mapped to DRF equivalents
    - Unexpected errors → 500 with correlation ID
    """
    request = context.get('request')
    correlation_id = getattr(request, 'correlation_id', 'unknown') if request else 'unknown'
    view = context.get('view')
    view_name = view.__class__.__name__ if view else 'unknown'

    # ==================== DJOYALTY CUSTOM ERRORS ====================
    if isinstance(exc, DjoyaltyError):
        logger.warning(
            'DjoyaltyError [%s] in %s: %s | correlation_id=%s',
            exc.code, view_name, exc.message, correlation_id,
        )
        return Response(
            {
                'error': exc.code,
                'message': exc.message,
                'correlation_id': correlation_id,
                **exc.extra,
            },
            status=exc.http_status,
        )

    # ==================== DJANGO VALIDATION ERROR ====================
    if isinstance(exc, DjangoValidationError):
        logger.warning('ValidationError in %s: %s', view_name, exc.message)
        return Response(
            {
                'error': 'validation_error',
                'message': exc.message if hasattr(exc, 'message') else str(exc),
                'correlation_id': correlation_id,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ==================== DJANGO 404 ====================
    if isinstance(exc, Http404):
        return Response(
            {
                'error': 'not_found',
                'message': 'The requested resource was not found.',
                'correlation_id': correlation_id,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ==================== DB INTEGRITY ERROR ====================
    if isinstance(exc, IntegrityError):
        logger.error('IntegrityError in %s: %s | correlation_id=%s', view_name, exc, correlation_id)
        return Response(
            {
                'error': 'integrity_error',
                'message': 'A database constraint was violated.',
                'correlation_id': correlation_id,
            },
            status=status.HTTP_409_CONFLICT,
        )

    # ==================== DRF STANDARD ERRORS ====================
    response = exception_handler(exc, context)

    if response is not None:
        # Wrap DRF response in standard format
        original_data = response.data
        error_code = 'api_error'
        message = 'An error occurred.'

        if isinstance(original_data, dict):
            if 'detail' in original_data:
                message = str(original_data['detail'])
                error_code = getattr(original_data.get('detail'), 'code', 'api_error')
            elif 'non_field_errors' in original_data:
                message = str(original_data['non_field_errors'][0])
                error_code = 'validation_error'

        response.data = {
            'error': error_code,
            'message': message,
            'details': original_data if isinstance(original_data, dict) else {'errors': original_data},
            'correlation_id': correlation_id,
        }
        logger.warning(
            'API error %d in %s: %s | correlation_id=%s',
            response.status_code, view_name, message, correlation_id,
        )
        return response

    # ==================== UNEXPECTED ERROR ====================
    logger.error(
        'Unhandled exception in %s: %s | correlation_id=%s',
        view_name, exc, correlation_id, exc_info=True,
    )
    return Response(
        {
            'error': 'internal_server_error',
            'message': 'An unexpected error occurred. Please try again.',
            'correlation_id': correlation_id,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

"""
NEW FILE — Global DRF exception handler.

Implements consistent error responses (Missing Component / API-layer
fix): previously errors bubbled up in DRF's default shape inconsistently
across viewsets, with no uniform `{"error": ..., "code": ...}` envelope.
"""
import logging
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('feature_flags')


def custom_exception_handler(exc, context):
    """Wrap DRF's default handler output in a consistent envelope and log it."""
    response = drf_exception_handler(exc, context)

    if response is not None:
        detail = response.data.get('detail') if isinstance(response.data, dict) else response.data
        response.data = {
            'error': detail if detail is not None else response.data,
            'code': response.status_code,
        }
        if response.status_code >= 500:
            logger.error('Unhandled exception: %s', exc, exc_info=True)

    return response

# api/admin_panel/error_handlers.py
"""Custom 400/403/404/500 error handlers for admin_panel."""
from django.http import JsonResponse
from django.utils import timezone


def bad_request(request, exception=None):
    return JsonResponse({
        'success': False, 'status': 400,
        'error': 'Bad Request',
        'message': str(exception)[:200] if exception else 'Invalid request',
        'timestamp': timezone.now().isoformat(),
    }, status=400)


def permission_denied(request, exception=None):
    return JsonResponse({
        'success': False, 'status': 403,
        'error': 'Forbidden',
        'message': 'You do not have permission to perform this action.',
        'timestamp': timezone.now().isoformat(),
    }, status=403)


def page_not_found(request, exception=None):
    return JsonResponse({
        'success': False, 'status': 404,
        'error': 'Not Found',
        'message': f'Endpoint {request.path} not found.',
        'timestamp': timezone.now().isoformat(),
    }, status=404)


def server_error(request):
    import logging
    logging.getLogger(__name__).error(f'500 Internal Server Error: {request.path}')
    return JsonResponse({
        'success': False, 'status': 500,
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred. Our team has been notified.',
        'timestamp': timezone.now().isoformat(),
    }, status=500)
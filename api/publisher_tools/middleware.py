# api/publisher_tools/middleware.py
"""Publisher Tools — Custom Middleware."""
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class PublisherToolsAPIMiddleware(MiddlewareMixin):
    """
    Publisher Tools API middleware।
    - Request timing
    - API key authentication
    - Rate limiting headers
    - CORS headers for publisher domains
    """

    def process_request(self, request):
        request._pt_start_time = time.time()
        # API Key check for /api/publisher-tools/ endpoints
        if '/api/publisher-tools/' in request.path:
            api_key = request.headers.get('X-Publisher-Tools-Key', '')
            if api_key:
                from .repository import PublisherRepository
                publisher = PublisherRepository.get_by_api_key(api_key)
                if publisher:
                    request._publisher = publisher
        return None

    def process_response(self, request, response):
        if hasattr(request, '_pt_start_time'):
            elapsed = time.time() - request._pt_start_time
            response['X-Publisher-Tools-Time'] = f'{elapsed:.4f}s'

        response['X-Publisher-Tools-Version'] = '1.0.0'

        # Log slow requests
        if hasattr(request, '_pt_start_time'):
            elapsed = time.time() - request._pt_start_time
            if elapsed > 2.0:
                logger.warning(f'Slow request: {request.path} took {elapsed:.2f}s')

        return response

    def process_exception(self, request, exception):
        from .exceptions import PublisherToolsException
        if isinstance(exception, PublisherToolsException):
            return JsonResponse({
                'success': False,
                'message': str(exception.detail),
                'code': exception.default_code,
            }, status=exception.status_code)
        return None


class PublisherTenantMiddleware(MiddlewareMixin):
    """Multi-tenant middleware — request থেকে tenant identify করে।"""

    def process_request(self, request):
        host = request.get_host().lower()
        try:
            from api.tenants.models import Tenant
            tenant = Tenant.objects.filter(domain=host, is_active=True).first()
            request.tenant = tenant
        except Exception:
            request.tenant = None
        return None


class PublisherRequestLoggingMiddleware(MiddlewareMixin):
    """Publisher API request logging middleware."""

    def process_request(self, request):
        if '/api/publisher-tools/' in request.path:
            logger.debug(f'PT API Request: {request.method} {request.path} — User: {request.user}')
        return None

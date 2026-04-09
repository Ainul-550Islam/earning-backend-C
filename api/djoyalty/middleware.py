# api/djoyalty/middleware.py
"""
Production middleware for Djoyalty:
- Request/response logging
- Tenant injection
- Performance timing
- Correlation ID tracking
"""
import time
import uuid
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('djoyalty.middleware')


class DjoyaltyRequestMiddleware(MiddlewareMixin):
    """
    Main Djoyalty request middleware:
    1. Correlation ID injection (X-Correlation-ID)
    2. Request timing
    3. Structured request logging
    4. Tenant injection from header/subdomain
    """

    def process_request(self, request):
        # Correlation ID — track request across microservices
        correlation_id = (
            request.META.get('HTTP_X_CORRELATION_ID')
            or request.META.get('HTTP_X_REQUEST_ID')
            or str(uuid.uuid4())
        )
        request.correlation_id = correlation_id
        request._start_time = time.monotonic()
        request._loyalty_events = []

        # Inject tenant from header (X-Tenant-ID) or subdomain
        if not hasattr(request, 'tenant') or request.tenant is None:
            self._inject_tenant(request)

        logger.debug(
            'Djoyalty request: %s %s | correlation_id=%s',
            request.method, request.path, correlation_id,
        )

    def process_response(self, request, response):
        # Add correlation ID to response header
        correlation_id = getattr(request, 'correlation_id', '')
        if correlation_id:
            response['X-Correlation-ID'] = correlation_id

        # Request timing
        start = getattr(request, '_start_time', None)
        if start:
            duration_ms = (time.monotonic() - start) * 1000
            response['X-Response-Time'] = f'{duration_ms:.1f}ms'
            if duration_ms > 1000:
                logger.warning(
                    'Slow Djoyalty request: %s %s took %.0fms | correlation_id=%s',
                    request.method, request.path, duration_ms, correlation_id,
                )

        # Flush queued loyalty events
        events = getattr(request, '_loyalty_events', [])
        for event in events:
            try:
                from .events.event_dispatcher import EventDispatcher
                EventDispatcher.dispatch(
                    event['event_type'],
                    customer=event.get('customer'),
                    data=event.get('data', {}),
                )
            except Exception as e:
                logger.error('Event flush error: %s', e)

        return response

    def _inject_tenant(self, request):
        """Inject tenant from X-Tenant-ID header।"""
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            try:
                from tenants.models import Tenant
                request.tenant = Tenant.objects.filter(id=tenant_id).first()
            except Exception:
                request.tenant = None


class DjoyaltySecurityMiddleware(MiddlewareMixin):
    """Security headers for Djoyalty API responses।"""

    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Cache-Control': 'no-store',
    }

    def process_response(self, request, response):
        for header, value in self.SECURITY_HEADERS.items():
            if header not in response:
                response[header] = value
        return response


class DjoyaltyAPIVersionMiddleware(MiddlewareMixin):
    """
    API version tracking।
    X-API-Version: 1.0 header inject করে।
    """
    from .constants import DJOYALTY_VERSION

    def process_response(self, request, response):
        from .constants import DJOYALTY_VERSION
        response['X-Djoyalty-Version'] = DJOYALTY_VERSION
        return response

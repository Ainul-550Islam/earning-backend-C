"""
DR Integration Middleware — Auto-log all API requests to DR immutable audit log.
"""
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

SKIP_PATHS = {'/health/', '/metrics/', '/static/', '/media/', '/favicon.ico', '/admin/jsi18n/'}


class DRAuditMiddleware(MiddlewareMixin):
    """
    Middleware that logs all API requests to the DR immutable audit log.
    Replaces manual logging in api/audit_logs/middleware.py.

    Add to MIDDLEWARE after authentication middleware:
        'dr_integration.middleware.DRAuditMiddleware',
    """

    def process_request(self, request):
        request._dr_start_time = time.monotonic()
        return None

    def process_response(self, request, response):
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return response

        # Only log authenticated users or failed auth
        if not hasattr(request, 'user'):
            return response

        duration_ms = round((time.monotonic() - getattr(request, '_dr_start_time', time.monotonic())) * 1000, 2)

        # Only log mutating or sensitive requests
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') or response.status_code in (401, 403, 500):
            try:
                from dr_integration.services import DRAuditBridge
                bridge = DRAuditBridge()
                bridge.log(
                    actor_id=str(request.user.id) if request.user.is_authenticated else 'anonymous',
                    action=f"{request.method}:{request.path}",
                    resource_type=self._get_resource_type(request.path),
                    ip_address=self._get_client_ip(request),
                    result='success' if response.status_code < 400 else (
                        'denied' if response.status_code == 403 else 'failure'
                    ),
                    error_message=f"HTTP {response.status_code}" if response.status_code >= 400 else None,
                    request_id=request.META.get('HTTP_X_REQUEST_ID'),
                    actor_type='user' if request.user.is_authenticated else 'anonymous',
                )
            except Exception as e:
                logger.debug(f"DR audit middleware error: {e}")
        return response

    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def _get_resource_type(self, path: str) -> str:
        """Extract resource type from URL path."""
        parts = [p for p in path.split('/') if p and p != 'api']
        return parts[0] if parts else 'unknown'

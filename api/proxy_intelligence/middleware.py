"""
Proxy Intelligence Middleware
==============================
Automatically checks incoming requests against the proxy intelligence system.
Can block VPNs, proxies, and blacklisted IPs before they reach views.
"""
import logging
import time
from django.http import JsonResponse
from django.conf import settings
from .utilities.ip_validator import IPValidator
from .services import BlacklistService, VelocityService

logger = logging.getLogger(__name__)

# Settings with defaults
PI_SETTINGS = getattr(settings, 'PROXY_INTELLIGENCE', {})
BLOCK_TOR = PI_SETTINGS.get('BLOCK_TOR', False)
BLOCK_VPN = PI_SETTINGS.get('BLOCK_VPN', False)
BLOCK_PROXIES = PI_SETTINGS.get('BLOCK_PROXIES', False)
LOG_REQUESTS = PI_SETTINGS.get('LOG_REQUESTS', True)
EXCLUDED_PATHS = PI_SETTINGS.get('EXCLUDED_PATHS', ['/admin/', '/health/', '/static/'])
VELOCITY_CHECK = PI_SETTINGS.get('VELOCITY_CHECK', True)
RATE_LIMIT_PER_MINUTE = PI_SETTINGS.get('RATE_LIMIT_PER_MINUTE', 120)


class ProxyIntelligenceMiddleware:
    """
    Django middleware that runs IP intelligence checks on every request.

    Add to MIDDLEWARE in settings.py:
        'api.proxy_intelligence.middleware.ProxyIntelligenceMiddleware'

    Configure in settings.py:
        PROXY_INTELLIGENCE = {
            'BLOCK_TOR': True,
            'BLOCK_VPN': False,
            'BLOCK_PROXIES': False,
            'LOG_REQUESTS': True,
            'RATE_LIMIT_PER_MINUTE': 120,
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip excluded paths
        if any(request.path.startswith(p) for p in EXCLUDED_PATHS):
            return self.get_response(request)

        ip_address = IPValidator.extract_from_request(request)

        # Skip private/loopback IPs (e.g., internal services)
        if IPValidator.is_should_skip(ip_address):
            return self.get_response(request)

        tenant = getattr(request, 'tenant', None)

        # 1. Check velocity / rate limiting
        if VELOCITY_CHECK:
            exceeded = VelocityService.record_and_check(
                ip_address=ip_address,
                action_type='http_request',
                threshold=RATE_LIMIT_PER_MINUTE,
                window_seconds=60,
                tenant=tenant,
            )
            if exceeded:
                return self._rate_limit_response(ip_address)

        # 2. Check blacklist
        if BlacklistService.is_blacklisted(ip_address, tenant):
            return self._blocked_response(ip_address, 'blacklisted')

        # 3. Check whitelist (skip further checks if whitelisted)
        if BlacklistService.is_whitelisted(ip_address, tenant):
            response = self.get_response(request)
            return response

        # Attach IP info to request for views to use
        request.client_ip = ip_address

        start = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start) * 1000

        # 4. Log request asynchronously (best effort)
        if LOG_REQUESTS:
            self._log_request(request, ip_address, response.status_code, duration_ms)

        return response

    @staticmethod
    def _blocked_response(ip_address: str, reason: str) -> JsonResponse:
        logger.warning(f"Blocked request from {ip_address}: {reason}")
        return JsonResponse(
            {'error': 'Access denied.', 'reason': reason, 'ip': ip_address},
            status=403
        )

    @staticmethod
    def _rate_limit_response(ip_address: str) -> JsonResponse:
        return JsonResponse(
            {'error': 'Rate limit exceeded. Please slow down.', 'ip': ip_address},
            status=429
        )

    @staticmethod
    def _log_request(request, ip_address: str, status_code: int, duration_ms: float):
        try:
            from .services import APIRequestLogger
            APIRequestLogger.log(
                ip_address=ip_address,
                endpoint=request.path,
                method=request.method,
                status_code=status_code,
                response_time_ms=round(duration_ms, 2),
                user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                tenant=getattr(request, 'tenant', None),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.debug(f"Request logging failed: {e}")

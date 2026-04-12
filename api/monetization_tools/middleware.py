"""
api/monetization_tools/middleware.py
=======================================
Request-level middleware for monetization features.
"""

import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class MonetizationTimingMiddleware(MiddlewareMixin):
    """
    Log response time for all /api/monetization_tools/ endpoints.
    Useful for performance monitoring.
    """
    MONITORED_PREFIX = '/api/monetization_tools/'

    def process_request(self, request):
        if request.path.startswith(self.MONITORED_PREFIX):
            request._mt_start_time = time.monotonic()

    def process_response(self, request, response):
        start = getattr(request, '_mt_start_time', None)
        if start is not None:
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms > 500:
                logger.warning(
                    "SLOW monetization request: %s %s → %.1fms",
                    request.method, request.path, elapsed_ms,
                )
            response['X-MT-Response-Time'] = f"{elapsed_ms:.1f}ms"
        return response


class AdNetworkPostbackMiddleware(MiddlewareMixin):
    """
    Middleware to log and pre-validate incoming ad-network postback requests.
    Attaches `request.is_postback = True` for /postback/ paths.
    """
    POSTBACK_PATHS = ['/api/monetization_tools/completions/', '/postback/']

    def process_request(self, request):
        request.is_postback = any(
            request.path.startswith(p) for p in self.POSTBACK_PATHS
        )
        if request.is_postback:
            network = request.GET.get('network', 'unknown')
            logger.debug(
                "Postback received: network=%s ip=%s path=%s",
                network,
                request.META.get('REMOTE_ADDR', ''),
                request.path,
            )


class MonetizationRateLimitMiddleware(MiddlewareMixin):
    """
    Lightweight in-memory rate limit for monetization write endpoints.
    For production use api/rate_limit app or Django Ratelimit.
    """
    WRITE_METHODS  = {'POST', 'PUT', 'PATCH', 'DELETE'}
    RATE_LIMIT_KEY = 'mt_rate:{ip}'
    MAX_REQUESTS   = 60    # per window
    WINDOW_SECONDS = 60

    def process_request(self, request):
        if request.method not in self.WRITE_METHODS:
            return None
        if not request.path.startswith('/api/monetization_tools/'):
            return None

        from django.core.cache import cache
        from django.http import JsonResponse

        ip  = request.META.get('REMOTE_ADDR', '127.0.0.1')
        key = self.RATE_LIMIT_KEY.format(ip=ip)

        count = cache.get(key, 0)
        if count >= self.MAX_REQUESTS:
            return JsonResponse(
                {'success': False, 'message': 'Rate limit exceeded. Try again later.'},
                status=429,
            )
        cache.set(key, count + 1, timeout=self.WINDOW_SECONDS)
        return None

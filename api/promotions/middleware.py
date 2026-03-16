# =============================================================================
# api/promotions/middleware.py
# Custom Middleware — Security, Device Fingerprint, Request Logging
# =============================================================================

import logging
import time

from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .constants import HEADER_DEVICE_FINGERPRINT, HEADER_APP_VERSION, HEADER_PLATFORM

logger = logging.getLogger('promotions.middleware')


class DeviceFingerprintMiddleware(MiddlewareMixin):
    """
    Request header থেকে device fingerprint extract করে request এ attach করে।
    Client-side (FingerprintJS) থেকে X-Device-Fingerprint header পাঠাতে হবে।
    """

    def process_request(self, request):
        fingerprint = request.META.get(
            f'HTTP_{HEADER_DEVICE_FINGERPRINT.upper().replace("-", "_")}', ''
        ).strip()
        request.device_fingerprint = fingerprint or None
        request.app_version        = request.META.get(
            f'HTTP_{HEADER_APP_VERSION.upper().replace("-", "_")}', ''
        )
        request.client_platform    = request.META.get(
            f'HTTP_{HEADER_PLATFORM.upper().replace("-", "_")}', ''
        )


class BlacklistIPMiddleware(MiddlewareMixin):
    """
    Blacklisted IP থেকে আসা request গুলো early block করে।
    API endpoints ছাড়া অন্য request এ skip করে।
    """

    EXEMPT_PATHS = ['/admin/', '/health/', '/static/', '/media/']

    def process_request(self, request):
        # Non-API path skip করো
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return None

        ip = self._get_client_ip(request)
        if not ip:
            return None

        # Cache check (performance জন্য DB hit এড়ানো)
        from django.core.cache import cache
        from .constants import CACHE_KEY_BLACKLIST_IP

        cache_key = CACHE_KEY_BLACKLIST_IP.format(ip)
        is_blocked = cache.get(cache_key)

        if is_blocked is None:
            from .models import Blacklist
            is_blocked = Blacklist.is_blacklisted('ip', ip)
            cache.set(cache_key, is_blocked, timeout=300)  # 5 min cache

        if is_blocked:
            from django.http import JsonResponse
            logger.warning(f'Blocked request from blacklisted IP: {ip} | Path: {request.path}')
            return JsonResponse(
                {'error': 'Access denied.', 'code': 'blacklisted'},
                status=403,
            )
        return None

    @staticmethod
    def _get_client_ip(request) -> str | None:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class RequestTimingMiddleware(MiddlewareMixin):
    """API response time log করে — performance monitoring এর জন্য।"""

    def process_request(self, request):
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            duration_ms = (time.monotonic() - request._start_time) * 1000
            response['X-Response-Time-Ms'] = str(round(duration_ms, 2))

            # Slow request warning (>2 seconds)
            if duration_ms > 2000:
                logger.warning(
                    f'SLOW REQUEST: {request.method} {request.path} '
                    f'took {duration_ms:.0f}ms | User: {getattr(request.user, "pk", "anon")}'
                )
        return response

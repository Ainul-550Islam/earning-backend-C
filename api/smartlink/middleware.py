import time
import logging
from django.core.cache import cache
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings
from .constants import (
    CACHE_PREFIX_SMARTLINK, CACHE_TTL_SMARTLINK,
    API_RATE_LIMIT_REDIRECT, CACHE_PREFIX_FRAUD,
)

logger = logging.getLogger('smartlink.redirect')
perf_logger = logging.getLogger('smartlink.performance')


class SmartLinkRedirectMiddleware:
    """
    High-performance middleware for slug-based redirects.
    Handles /go/<slug>/ routes before Django view routing.
    Target: <5ms per redirect using Redis cache.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.redirect_prefix = getattr(settings, 'SMARTLINK_REDIRECT_PREFIX', '/go/')

    def __call__(self, request):
        start_time = time.perf_counter()

        if request.path.startswith(self.redirect_prefix):
            slug = request.path[len(self.redirect_prefix):].strip('/')
            if slug:
                response = self._handle_redirect(request, slug)
                if response:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    perf_logger.debug(
                        f"Middleware redirect [{slug}] → {elapsed_ms:.2f}ms"
                    )
                    response['X-SmartLink-Time'] = f"{elapsed_ms:.2f}ms"
                    return response

        response = self.get_response(request)
        return response

    def _handle_redirect(self, request, slug):
        """
        Attempt ultra-fast cache-based redirect.
        Falls through to view if cache miss or complex targeting needed.
        """
        cache_key = f"{CACHE_PREFIX_SMARTLINK}{slug}:simple"
        cached = cache.get(cache_key)

        if cached:
            ip = self._get_ip(request)
            if self._is_ip_blocked(ip):
                return HttpResponse("Blocked", status=403)
            return HttpResponseRedirect(cached)

        # Cache miss → let the view handle it (will cache result)
        return None

    def _get_ip(self, request) -> str:
        for header in ('HTTP_CF_IPCOUNTRY', 'HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'):
            ip = request.META.get(header)
            if ip:
                return ip.split(',')[0].strip()
        return '0.0.0.0'

    def _is_ip_blocked(self, ip: str) -> bool:
        """Check Redis for blocked IP (fraud system)."""
        return bool(cache.get(f"{CACHE_PREFIX_FRAUD}blocked:{ip}"))


class SmartLinkPerformanceMiddleware:
    """
    Logs performance metrics for SmartLink API endpoints.
    Adds X-SmartLink-Time header to all smartlink API responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.monitored_prefixes = ('/api/smartlink/', '/go/')

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.monitored_prefixes):
            start = time.perf_counter()
            response = self.get_response(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response['X-SmartLink-Time'] = f"{elapsed_ms:.2f}ms"

            if elapsed_ms > 100:
                perf_logger.warning(
                    f"Slow SmartLink request: {request.path} → {elapsed_ms:.2f}ms"
                )
            return response

        return self.get_response(request)

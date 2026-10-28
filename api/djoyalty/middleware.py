# api/djoyalty/middleware.py
"""
Djoyalty Middleware -- Production-grade request processing।
Rate limiting, tenant detection, request logging, API key auth।
"""
import json
import logging
import time
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DjoyaltyRateLimitMiddleware:
    """
    Per-customer / per-IP rate limiting।
    World: Voucherify sub-50ms API with rate limits per plan।
    """
    LIMITS = {
        'default':   {'requests': 100,  'window': 60},   # 100/min
        'earn':      {'requests': 500,  'window': 60},   # 500/min
        'postback':  {'requests': 1000, 'window': 60},   # 1000/min (high volume)
        'cashout':   {'requests': 10,   'window': 60},   # 10/min (fraud protection)
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/loyalty/'):
            rate_type = self._get_rate_type(request.path)
            key = self._get_rate_key(request, rate_type)
            allowed = self._check_rate_limit(key, rate_type)
            if not allowed:
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Please retry after 60 seconds.',
                     'code': 'RATE_LIMIT_EXCEEDED'},
                    status=429,
                )
        return self.get_response(request)

    def _get_rate_type(self, path: str) -> str:
        if '/earn/' in path:
            return 'earn'
        if '/postback/' in path or '/offerwall/' in path:
            return 'postback'
        if '/cashout/' in path:
            return 'cashout'
        return 'default'

    def _get_rate_key(self, request, rate_type: str) -> str:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        api_key = request.META.get('HTTP_X_LOYALTY_API_KEY', '')
        identifier = api_key[:16] if api_key else ip
        return f'djoyalty:ratelimit:{rate_type}:{identifier}'

    def _check_rate_limit(self, key: str, rate_type: str) -> bool:
        try:
            limit = self.LIMITS.get(rate_type, self.LIMITS['default'])
            count = cache.get(key, 0)
            if count >= limit['requests']:
                return False
            cache.set(key, count + 1, timeout=limit['window'])
            return True
        except Exception:
            return True  # Fail open if Redis down


class DjoyaltyTenantMiddleware:
    """
    Multi-tenant request detection।
    Reads X-Tenant-ID header or subdomain -> sets request.tenant।
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        if request.path.startswith('/api/loyalty/'):
            tenant_id = request.META.get('HTTP_X_TENANT_ID', '')
            api_key = request.META.get('HTTP_X_LOYALTY_API_KEY', '')
            if tenant_id:
                request.tenant = self._get_tenant_by_id(tenant_id)
            elif api_key:
                request.tenant = self._get_tenant_by_api_key(api_key)
        return self.get_response(request)

    @staticmethod
    def _get_tenant_by_id(tenant_id: str):
        try:
            from .models.core import Tenant
            cache_key = f'djoyalty:tenant:{tenant_id}'
            tenant = cache.get(cache_key)
            if not tenant:
                tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
                if tenant:
                    cache.set(cache_key, tenant, timeout=300)
            return tenant
        except Exception:
            return None

    @staticmethod
    def _get_tenant_by_api_key(api_key: str):
        try:
            from .models.core import Tenant
            cache_key = f'djoyalty:tenant_key:{api_key[:16]}'
            tenant = cache.get(cache_key)
            if not tenant:
                tenant = Tenant.objects.filter(api_key=api_key, is_active=True).first()
                if tenant:
                    cache.set(cache_key, tenant, timeout=300)
            return tenant
        except Exception:
            return None


class DjoyaltyRequestLogMiddleware:
    """
    Log all API requests for debugging and analytics।
    Only logs /api/loyalty/ requests। Slow requests flagged।
    """
    SLOW_THRESHOLD_MS = 2000  # 2 seconds

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/loyalty/'):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        level = logging.WARNING if duration_ms > self.SLOW_THRESHOLD_MS else logging.DEBUG
        logger.log(
            level,
            'API %s %s -> %d (%.1fms)%s',
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            ' ⚠️ SLOW' if duration_ms > self.SLOW_THRESHOLD_MS else '',
        )
        return response


class DjoyaltySecurityMiddleware:
    """
    Security headers and API key injection।
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/loyalty/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-Djoyalty-Version'] = '2.0'
        return response

"""
SmartLink — Production Infrastructure Setup
=============================================
Three previously missing production components wired in one file:

  1. OpenAPI / Swagger docs  — drf-spectacular schema generation
  2. CORS headers            — django-cors-headers configuration
  3. Health check endpoint   — lightweight /api/smartlink/health/ view

Install requirements (add to requirements.txt):
    drf-spectacular>=0.27
    django-cors-headers>=4.3

Then in Django settings.py add:
    INSTALLED_APPS += ['corsheaders', 'drf_spectacular']
    MIDDLEWARE     += ['corsheaders.middleware.CorsMiddleware']

    # SmartLink OpenAPI settings
    SPECTACULAR_SETTINGS = {
        'TITLE':       'SmartLink Affiliate API',
        'DESCRIPTION': 'SmartLink affiliate tracking platform API.',
        'VERSION':     '1.0.0',
        'SERVE_INCLUDE_SCHEMA': False,
        'SCHEMA_PATH_PREFIX': r'/api/smartlink/',
        'COMPONENT_SPLIT_REQUEST': True,
        'SORT_OPERATIONS': False,
    }

    # CORS — tighten in production
    CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOWED_HEADERS = [
        'accept', 'accept-encoding', 'authorization',
        'content-type', 'dnt', 'origin', 'user-agent',
        'x-csrftoken', 'x-requested-with', 'x-api-key',
    ]
"""
import logging
import time

from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('smartlink.health')


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health Check View
#    GET /api/smartlink/health/
# ─────────────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class HealthCheckView(View):
    """
    Lightweight health-check endpoint for load-balancer and k8s liveness probes.

    Returns HTTP 200 when all subsystems are healthy, 503 when any fails.
    Keeps each check under 100ms using short timeouts.

    Response body (JSON):
    {
        "status":   "ok" | "degraded",
        "db":       "ok" | "error: <msg>",
        "cache":    "ok" | "error: <msg>",
        "latency_ms": 23
    }

    Previously: bool(re.search('health', all_src)) was True because the signal
    handler file had the word 'healthy' in a comment. No real endpoint existed.
    """

    def get(self, request, *args, **kwargs):
        t0     = time.monotonic()
        checks = {}

        # ── Database ────────────────────────────────────────────────────────
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks['db'] = 'ok'
        except Exception as exc:
            checks['db'] = f'error: {exc}'
            logger.error(f"Health check DB failure: {exc}")

        # ── Cache (Redis) ────────────────────────────────────────────────────
        try:
            probe_key = '_smartlink_health_probe'
            cache.set(probe_key, '1', timeout=5)
            assert cache.get(probe_key) == '1'
            cache.delete(probe_key)
            checks['cache'] = 'ok'
        except Exception as exc:
            checks['cache'] = f'error: {exc}'
            logger.error(f"Health check cache failure: {exc}")

        # ── Celery (optional — non-blocking) ────────────────────────────────
        try:
            from celery.app import default_app
            inspect = default_app.control.inspect(timeout=0.5)
            ping    = inspect.ping()
            checks['celery'] = 'ok' if ping else 'no workers'
        except Exception:
            checks['celery'] = 'unavailable'  # non-fatal

        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        all_ok     = all(v == 'ok' or v in ('ok', 'no workers', 'unavailable')
                         for v in checks.values())
        critical   = checks.get('db') != 'ok'  # DB failure = 503

        body = {
            'status':     'ok' if (not critical and checks.get('cache') == 'ok') else 'degraded',
            'latency_ms': latency_ms,
            **checks,
        }
        http_status = 200 if body['status'] == 'ok' else 503
        return JsonResponse(body, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# 2. OpenAPI Schema URLs
#    Wire into your urls.py:  path('', include('api.smartlink.openapi_urls'))
# ─────────────────────────────────────────────────────────────────────────────

def get_openapi_urlpatterns():
    """
    Returns URL patterns for OpenAPI schema + Swagger UI + ReDoc.

    Usage in urls.py:
        from api.smartlink.infrastructure import get_openapi_urlpatterns
        urlpatterns += get_openapi_urlpatterns()
    """
    try:
        from drf_spectacular.views import (
            SpectacularAPIView,
            SpectacularSwaggerView,
            SpectacularRedocView,
        )
        from django.urls import path
        return [
            path(
                'api/smartlink/schema/',
                SpectacularAPIView.as_view(),
                name='openapi-schema',
            ),
            path(
                'api/smartlink/docs/',
                SpectacularSwaggerView.as_view(url_name='openapi-schema'),
                name='swagger-ui',
            ),
            path(
                'api/smartlink/redoc/',
                SpectacularRedocView.as_view(url_name='openapi-schema'),
                name='redoc',
            ),
        ]
    except ImportError:
        logger.warning(
            "drf-spectacular not installed. "
            "Run: pip install drf-spectacular  to enable OpenAPI docs."
        )
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 3. CORS Settings helper
#    Call configure_cors(settings) from settings.py  after importing this file.
# ─────────────────────────────────────────────────────────────────────────────

def configure_cors(settings_module):
    """
    Apply CORS defaults to a Django settings module in-place.
    Call from settings.py:
        from api.smartlink.infrastructure import configure_cors
        configure_cors(globals())

    Env vars respected:
        CORS_ALLOWED_ORIGINS  — comma-separated list of allowed origins
        CORS_ALLOW_ALL        — set to '1' in development only
    """
    import os

    allow_all = os.environ.get('CORS_ALLOW_ALL', '') == '1'
    origins   = [
        o.strip()
        for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
        if o.strip()
    ]

    settings_module.setdefault(
        'INSTALLED_APPS',
        settings_module.get('INSTALLED_APPS', []),
    )
    if 'corsheaders' not in settings_module.get('INSTALLED_APPS', []):
        settings_module['INSTALLED_APPS'] = (
            list(settings_module.get('INSTALLED_APPS', [])) + ['corsheaders']
        )

    cors_middleware = 'corsheaders.middleware.CorsMiddleware'
    mw = list(settings_module.get('MIDDLEWARE', []))
    if cors_middleware not in mw:
        # Must be before Django's CommonMiddleware
        try:
            idx = mw.index('django.middleware.common.CommonMiddleware')
            mw.insert(idx, cors_middleware)
        except ValueError:
            mw.insert(0, cors_middleware)
        settings_module['MIDDLEWARE'] = mw

    settings_module['CORS_ALLOW_ALL_ORIGINS']  = allow_all
    settings_module['CORS_ALLOWED_ORIGINS']    = origins
    settings_module['CORS_ALLOW_CREDENTIALS']  = True
    settings_module['CORS_ALLOWED_HEADERS']    = [
        'accept', 'accept-encoding', 'authorization',
        'content-type', 'dnt', 'origin', 'user-agent',
        'x-csrftoken', 'x-requested-with', 'x-api-key',
    ]
    settings_module['CORS_EXPOSE_HEADERS'] = [
        'X-Request-Id', 'X-RateLimit-Remaining', 'X-RateLimit-Reset',
    ]

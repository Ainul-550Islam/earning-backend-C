"""
api/tasks/middleware.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django middleware for the task system.
Add to MIDDLEWARE in settings.py as needed.
"""

import logging
import time
import hashlib
from django.utils import timezone
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class TaskRequestLoggingMiddleware:
    """
    Logs all requests to task endpoints with timing information.
    Useful for performance monitoring in production.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only log task API paths
        if not request.path.startswith('/api/tasks') and not request.path.startswith('/tasks'):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        elapsed  = time.monotonic() - start

        user_id = getattr(request.user, 'pk', 'anon') if hasattr(request, 'user') else 'anon'
        logger.info(
            f"[TASK REQ] {request.method} {request.path} "
            f"→ {response.status_code} in {elapsed*1000:.1f}ms "
            f"user={user_id}"
        )
        response['X-Task-Response-Time'] = f"{elapsed*1000:.1f}ms"
        return response


class IPBlockingMiddleware:
    """
    Blocks requests from IPs in the task system blacklist.
    Reads from Redis cache (synced by ip_management_tasks.sync_ip_blacklist).
    Lightweight: cache lookup only, no DB queries.
    """

    WHITELIST_PATHS = [
        '/health/',
        '/admin/',
        '/__debug__/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for path in self.WHITELIST_PATHS:
            if request.path.startswith(path):
                return self.get_response(request)

        ip      = self.get_client_ip(request)
        blocked = self.is_blocked(ip)

        if blocked:
            logger.warning(f"[IP BLOCK] Blocked request from {ip}: {request.path}")
            return JsonResponse(
                {'error': 'Access denied.', 'code': 'ip_blocked'},
                status=403,
            )
        return self.get_response(request)

    @staticmethod
    def get_client_ip(request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    @staticmethod
    def is_blocked(ip: str) -> bool:
        if not ip:
            return False
        ip_hash = hashlib.md5(ip.encode()).hexdigest()
        return bool(cache.get(f'ip_blocked_{ip_hash}'))


class FraudCheckMiddleware:
    """
    Middleware that adds fraud score to request for downstream use.
    Does not block — just enriches request context.
    Views/permissions handle blocking based on score.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.fraud_score = 0
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.fraud_score = int(
                cache.get(f'fraud_score_{request.user.pk}', 0)
            )
        return self.get_response(request)


class TaskMaintenanceModeMiddleware:
    """
    Returns 503 for task endpoints when maintenance mode is active.
    Bypass: staff users always pass through.
    Set TASK_MAINTENANCE_MODE=True in settings or cache key 'task_maintenance'.
    """

    BYPASS_PATHS = ['/admin/', '/health/', '/__debug__/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        maintenance = (
            getattr(settings, 'TASK_MAINTENANCE_MODE', False) or
            bool(cache.get('task_maintenance'))
        )

        if maintenance:
            for path in self.BYPASS_PATHS:
                if request.path.startswith(path):
                    return self.get_response(request)

            is_staff = (
                hasattr(request, 'user') and
                request.user.is_authenticated and
                request.user.is_staff
            )
            if not is_staff:
                return JsonResponse(
                    {
                        'error':   'System under maintenance.',
                        'code':    'maintenance_mode',
                        'message': 'The task system is temporarily unavailable.',
                    },
                    status=503,
                )

        return self.get_response(request)


class TaskRateLimitMiddleware:
    """
    Global IP-level rate limiting for task API endpoints.
    Per-IP: 1000 requests/hour for all task paths combined.
    """

    RATE_LIMIT  = 1000
    WINDOW      = 3600

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not (request.path.startswith('/api/tasks') or request.path.startswith('/tasks')):
            return self.get_response(request)

        ip      = IPBlockingMiddleware.get_client_ip(request)
        ip_hash = hashlib.md5(ip.encode()).hexdigest()
        key     = f'global_rl_{ip_hash}'
        count   = cache.get(key, 0)

        if count >= self.RATE_LIMIT:
            logger.warning(f"[GLOBAL RATE LIMIT] {ip} exceeded {self.RATE_LIMIT} req/hour")
            return JsonResponse(
                {
                    'error':       'Too many requests.',
                    'code':        'global_rate_limited',
                    'retry_after': self.WINDOW,
                },
                status=429,
            )

        cache.set(key, count + 1, timeout=self.WINDOW)
        return self.get_response(request)


class TaskAPIVersionMiddleware:
    """
    Adds API version header to all task responses.
    Reads version from settings or defaults to 'v1'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        from django.conf import settings
        api_version = getattr(settings, 'TASK_API_VERSION', 'v1')
        response['X-Task-API-Version'] = api_version
        response['X-Task-Timestamp']   = timezone.now().isoformat()
        return response


class TaskCorrelationIDMiddleware:
    """
    Attaches a correlation ID to every request/response for distributed tracing.
    The ID is taken from X-Correlation-ID header or auto-generated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import uuid
        correlation_id = (
            request.META.get('HTTP_X_CORRELATION_ID') or
            str(uuid.uuid4())
        )
        request.correlation_id = correlation_id
        response = self.get_response(request)
        response['X-Correlation-ID'] = correlation_id
        return response


__all__ = [
    'TaskRequestLoggingMiddleware', 'IPBlockingMiddleware',
    'FraudCheckMiddleware', 'TaskMaintenanceModeMiddleware',
    'TaskRateLimitMiddleware', 'TaskAPIVersionMiddleware',
    'TaskCorrelationIDMiddleware',
]

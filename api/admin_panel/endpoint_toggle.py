from django.db import models
from django.core.cache import cache
from django.http import JsonResponse


class EndpointToggle(models.Model):
    """Control each API endpoint on/off"""
    path = models.CharField(max_length=500, unique=True, db_index=True)
    method = models.CharField(max_length=10, default='ALL')
    group = models.CharField(max_length=100, default='other')
    label = models.CharField(max_length=200, blank=True)
    is_enabled = models.BooleanField(default=True)
    disabled_message = models.CharField(
        max_length=500,
        default='This feature is temporarily disabled.'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        ordering = ['group', 'path']

    def __str__(self):
        status = '✅' if self.is_enabled else '❌'
        return f"{status} [{self.method}] {self.path}"

    @classmethod
    def is_path_enabled(cls, path, method='GET'):
        cache_key = f"endpoint_toggle_{path}_{method}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            toggle = cls.objects.filter(
                path=path,
                is_enabled=False
            ).filter(
                models.Q(method='ALL') | models.Q(method=method)
            ).first()
            result = toggle is None
            cache.set(cache_key, result, 5)
            return result
        except Exception:
            return True

    @classmethod
    def get_message(cls, path, method='GET'):
        try:
            toggle = cls.objects.filter(
                path=path, is_enabled=False
            ).filter(
                models.Q(method='ALL') | models.Q(method=method)
            ).first()
            if toggle:
                return toggle.disabled_message
        except Exception:
            pass
        return 'This feature is temporarily disabled.'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(f"endpoint_toggle_{self.path}_{self.method}")
        cache.delete(f"endpoint_toggle_{self.path}_ALL")


class EndpointToggleMiddleware:
    """Middleware to check endpoint toggle before processing request"""

    SKIP_PATHS = [
        '/admin/', '/api/admin-panel/endpoint-toggles/',
        '/api/schema/', '/api/docs/', '/api/auth/login/',
        '/api/auth/token/', '/static/', '/media/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        method = request.method

        # Skip admin and toggle management paths
        if any(path.startswith(skip) for skip in self.SKIP_PATHS):
            return self.get_response(request)

        # Only check API paths - exact match
        if path.startswith('/api/'):
            try:
                from django.db.models import Q
                disabled = EndpointToggle.objects.filter(
                    is_enabled=False
                ).filter(
                    Q(method='ALL') | Q(method=method)
                )
                for toggle in disabled:
                    if path == toggle.path:
                        return JsonResponse({
                            'error': toggle.disabled_message,
                            'code': 'ENDPOINT_DISABLED',
                            'path': path,
                        }, status=503)
            except Exception:
                pass

        return self.get_response(request)

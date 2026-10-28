# api/admin_panel/rate_limit_middleware.py
"""Per-IP rate limiting middleware for admin endpoints."""
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

class AdminRateLimitMiddleware(MiddlewareMixin):
    """Block IPs that exceed rate limits on admin endpoints."""
    LIMIT   = 300  # requests per window
    WINDOW  = 60   # seconds

    def process_request(self, request):
        if not request.path.startswith('/api/admin'):
            return None
        ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
              or request.META.get('REMOTE_ADDR', '0.0.0.0'))
        key = f'admin_panel:ip_rate:{ip}'
        count = cache.get(key, 0) + 1
        cache.set(key, count, self.WINDOW)
        if count > self.LIMIT:
            return JsonResponse({'error': 'Rate limit exceeded. Try again later.'}, status=429)
        return None
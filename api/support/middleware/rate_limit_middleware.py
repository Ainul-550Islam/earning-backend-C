"""
api/support/middleware/rate_limit_middleware.py
FILE 70/70 — API Rate Limiting Middleware

Ticket creation rate limiting।
DDoS + spam protection।
"""
import logging
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    '/api/support/tickets/':           {'max': 5,  'window': 3600,  'msg': 'Max 5 tickets per hour.'},
    '/api/support/widget/bot/message/':{'max': 30, 'window': 60,    'msg': 'Slow down! Max 30 bot messages per minute.'},
    '/api/support/widget/chat/start/': {'max': 3,  'window': 3600,  'msg': 'Max 3 chat sessions per hour.'},
}


class SupportRateLimitMiddleware:
    """Rate limiting for support endpoints"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.user.is_authenticated:
            limit_config = RATE_LIMITS.get(request.path)
            if limit_config:
                if not self._check_rate_limit(request.user.id, request.path, limit_config):
                    return JsonResponse({
                        'error':   True,
                        'message': limit_config['msg'],
                        'code':    'RATE_LIMITED',
                    }, status=429)

        return self.get_response(request)

    def _check_rate_limit(self, user_id: int, path: str, config: dict) -> bool:
        key   = f'rate_limit:{user_id}:{path}'
        count = cache.get(key, 0)
        if count >= config['max']:
            return False
        cache.set(key, count + 1, timeout=config['window'])
        return True
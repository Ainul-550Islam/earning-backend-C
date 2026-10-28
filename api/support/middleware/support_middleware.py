"""
api/support/middleware/support_middleware.py
FILE 69/70 — Visitor Tracking Middleware

settings.py MIDDLEWARE-এ add করো:
    'support.middleware.support_middleware.VisitorTrackingMiddleware',
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = ['/admin/', '/api/support/widget/', '/static/', '/media/', '/favicon']


class VisitorTrackingMiddleware:
    """Track all page visits for proactive chat"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only track for authenticated users + non-API paths
        if (request.method == 'GET' and
                request.user.is_authenticated and
                not any(request.path.startswith(p) for p in EXCLUDED_PATHS) and
                response.status_code == 200):
            try:
                session_id = request.session.get('visitor_session_id')
                if not session_id:
                    from api.support.livechat.visitor_tracking import visitor_tracker
                    session_id = visitor_tracker.create_session(
                        user_id   = str(request.user.id),
                        ip        = self._get_ip(request),
                        user_agent= request.META.get('HTTP_USER_AGENT', ''),
                    )
                    request.session['visitor_session_id'] = session_id

                from api.support.livechat.visitor_tracking import visitor_tracker
                visitor_tracker.track_event(
                    event_type = 'page_view',
                    session_id = session_id,
                    user_id    = str(request.user.id),
                    page_url   = request.path,
                    data       = {'title': '', 'referrer': request.META.get('HTTP_REFERER', '')},
                )
            except Exception as e:
                logger.debug(f'Visitor tracking error: {e}')

        return response

    def _get_ip(self, request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
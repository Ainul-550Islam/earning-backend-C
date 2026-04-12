"""
Messaging Middleware — Production-grade request middleware.
"""
from __future__ import annotations
import logging
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class InboxUnreadCountMiddleware:
    """
    Injects request.unread_inbox_count and request.cpa_unread_count
    for authenticated users. Cached for 60s to avoid DB hit on every request.
    """
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.unread_inbox_count = 0
        request.cpa_unread_count   = 0

        if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
            try:
                from django.core.cache import cache
                uid = request.user.pk

                # General inbox unread
                key = f"inbox_unread:{uid}"
                count = cache.get(key)
                if count is None:
                    from .models import UserInbox
                    count = UserInbox.objects.filter(
                        user_id=uid, is_read=False, is_archived=False
                    ).count()
                    cache.set(key, count, timeout=60)
                request.unread_inbox_count = count

                # CPA notification unread
                cpa_key = f"cpa_unread:{uid}"
                cpa_count = cache.get(cpa_key)
                if cpa_count is None:
                    from .models import CPANotification
                    cpa_count = CPANotification.objects.filter(
                        recipient_id=uid, is_read=False, is_dismissed=False
                    ).count()
                    cache.set(cpa_key, cpa_count, timeout=60)
                request.cpa_unread_count = cpa_count

            except Exception as exc:
                logger.error("InboxUnreadCountMiddleware: %s", exc)

        return self.get_response(request)


class MessagingRequestTimingMiddleware:
    """
    Logs slow messaging API requests (> 500ms).
    Useful for identifying N+1 queries and performance issues.
    """
    SLOW_THRESHOLD_MS = 500

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith("/api/messaging/"):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        if duration_ms > self.SLOW_THRESHOLD_MS:
            logger.warning(
                "SLOW MESSAGING REQUEST: %s %s → %dms status=%d",
                request.method, request.path, duration_ms, response.status_code,
            )
        return response


class WebSocketRateLimitMiddleware:
    """
    Middleware that tracks WebSocket connection attempts per IP.
    Blocks IPs that are hammering the WS endpoint.
    """
    MAX_WS_CONNECTIONS_PER_IP = 50  # per minute

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith("/ws/messaging/"):
            try:
                from .utils.rate_limiter import sliding_window_check
                ip = self._get_client_ip(request)
                ok, count = sliding_window_check(
                    key=f"ws_connect:{ip}",
                    limit=self.MAX_WS_CONNECTIONS_PER_IP,
                    window_seconds=60,
                )
                if not ok:
                    from django.http import HttpResponse as HR
                    logger.warning("WS rate limit exceeded: ip=%s count=%d", ip, count)
                    return HR("Too Many WebSocket Connection Attempts", status=429)
            except Exception:
                pass

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

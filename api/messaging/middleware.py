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
        """
        Returns the IP address to rate-limit WS connections by.

        SECURITY: X-Forwarded-For is a plain HTTP header the CLIENT sets
        on their own request - trusting it unconditionally (as this used
        to do, always taking the first/leftmost entry) lets any client
        bypass the rate limit entirely by sending a different fake IP on
        every connection attempt, since each fake IP gets its own
        independent limit bucket.

        A header value only becomes trustworthy once a real, trusted
        reverse proxy in front of Django has appended to it, and exactly
        how many hops to trust depends on actual deployment topology
        (nginx / ALB / Cloudflare / none / a chain of several) - not
        something this standalone module can know on its own. So by
        default (MESSAGING_TRUSTED_PROXY_COUNT unset or 0) this always
        uses REMOTE_ADDR, which a client cannot forge directly since it's
        set by the TCP connection itself. That may end up being a
        load balancer's own IP if one exists and isn't configured here -
        which under-restricts (several real clients sharing one bucket)
        rather than being exploitable. Never the reverse.

        To trust X-Forwarded-For, set MESSAGING_TRUSTED_PROXY_COUNT in
        settings to the exact number of trusted reverse-proxy hops
        between the client and Django (e.g. 1 for a single nginx/ALB in
        front of the app). Each trusted hop appends its own view of the
        connecting peer's IP to the header, so with N trusted hops the
        real client IP is always the Nth entry counting from the right -
        never the leftmost, which is exactly the position an attacker
        controls by pre-seeding the header themselves before it ever
        reaches the first trusted hop. Reading from the right stays
        correct even if a client prepends extra fake entries, as long as
        the configured count matches the real number of trusted hops.
        """
        from django.conf import settings
        remote_addr = request.META.get("REMOTE_ADDR") or "unknown"
        trusted_proxy_count = getattr(settings, "MESSAGING_TRUSTED_PROXY_COUNT", 0) or 0

        if trusted_proxy_count < 1:
            return remote_addr

        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if not x_forwarded:
            return remote_addr

        hops = [h.strip() for h in x_forwarded.split(",") if h.strip()]
        if len(hops) < trusted_proxy_count:
            # Header is shorter than the configured trusted-hop count -
            # doesn't match the expected topology. Fail safe to
            # REMOTE_ADDR rather than guess which entry might be real.
            return remote_addr

        return hops[-trusted_proxy_count]
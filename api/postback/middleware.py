"""middleware.py – Postback security middleware."""
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Paths that bypass the postback middleware checks
POSTBACK_PATH_PREFIX = "/api/postback/"


class PostbackIPFilterMiddleware(MiddlewareMixin):
    """
    Global middleware that rejects requests to postback endpoints from
    IPs that have been globally blacklisted (e.g. known fraud sources).

    Configure in settings:
        POSTBACK_GLOBAL_IP_BLACKLIST = ["1.2.3.4", "5.6.7.0/24"]

    This is a coarse first-layer defence; per-network whitelisting is
    handled inside the processing pipeline.
    """

    def process_request(self, request):
        if not request.path.startswith(POSTBACK_PATH_PREFIX):
            return None

        from django.conf import settings
        from .utils.ip_checker import get_client_ip, is_ip_in_whitelist

        blacklist = getattr(settings, "POSTBACK_GLOBAL_IP_BLACKLIST", [])
        if not blacklist:
            return None

        ip = get_client_ip(request, trust_forwarded=False)
        if is_ip_in_whitelist(ip, blacklist):
            logger.warning(
                "PostbackIPFilterMiddleware: blocked globally blacklisted IP %s on %s",
                ip, request.path,
            )
            # Return 200 to avoid enumeration; silently drop
            return JsonResponse({"status": "received"}, status=200)

        return None


class PostbackAuditMiddleware(MiddlewareMixin):
    """
    Attaches timing and audit context to every postback request.
    Logs processing time after the response is generated.
    """

    def process_request(self, request):
        if request.path.startswith(POSTBACK_PATH_PREFIX):
            import time
            request._postback_start_time = time.monotonic()

    def process_response(self, request, response):
        start = getattr(request, "_postback_start_time", None)
        if start is not None:
            import time
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(
                "PostbackAudit: %s %s → %d in %.1fms",
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
            )
        return response

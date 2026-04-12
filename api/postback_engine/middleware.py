"""
middleware.py – Request middleware for Postback Engine.
"""
import logging
import time

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class PostbackEngineMiddleware:
    """
    Middleware for postback endpoints:
      - Request timing (X-Processing-Time header)
      - Structured request logging
      - Basic abuse protection (very large payloads)
    """
    MAX_PAYLOAD_BYTES = 1024 * 64  # 64 KB

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply to postback engine paths
        if not request.path.startswith("/api/postback_engine/"):
            return self.get_response(request)

        # Block oversized payloads
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        if content_length > self.MAX_PAYLOAD_BYTES:
            logger.warning(
                "Oversized postback payload: %d bytes from %s",
                content_length, request.META.get("REMOTE_ADDR"),
            )
            return JsonResponse(
                {"error": "Payload too large."},
                status=413,
            )

        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        response["X-Processing-Time"] = f"{elapsed_ms}ms"

        logger.debug(
            "PostbackEngine %s %s → %d (%dms)",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response

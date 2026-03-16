"""
webhooks.py – HTTP webhook handlers for postback ingestion.

Security contract:
  • Every request creates a PostbackLog immediately (before validation) so
    that even rejected / spoofed requests are auditable.
  • HTTP response is always 200 OK to prevent status-code enumeration by
    malicious networks; the result is communicated in the JSON body.
  • Signatures are verified asynchronously in the Celery task to minimise
    response latency while preserving security (the log records the raw data
    before processing).
  • Raw request body is read once, cached, and passed to the task as hex so
    the HMAC can be computed over the exact bytes received.
"""
import json
import logging
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse

from .constants import SIGNATURE_HEADER, TIMESTAMP_HEADER, NONCE_HEADER
from .exceptions import NetworkNotFoundException, NetworkInactiveException
from .services import receive_postback
from .utils.ip_checker import get_client_ip

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class PostbackWebhookView(View):
    """
    Accepts GET and POST postbacks from affiliate/CPA networks.

    URL: /api/postback/<network_key>/

    Both GET (query-string payload) and POST (JSON body) are supported
    because many networks use GET callbacks.
    """

    def get(self, request, network_key: str):
        return self._handle(request, network_key)

    def post(self, request, network_key: str):
        return self._handle(request, network_key)

    def _handle(self, request, network_key: str) -> JsonResponse:
        # Read raw body once (important for HMAC over exact bytes)
        try:
            body_bytes = request.body  # Django caches this
        except Exception:
            body_bytes = b""

        # Parse payload: JSON body (POST) or query params (GET)
        payload = self._parse_payload(request, body_bytes)

        # Extract security headers
        signature = request.META.get(
            "HTTP_" + SIGNATURE_HEADER.upper().replace("-", "_"), ""
        )
        timestamp_str = request.META.get(
            "HTTP_" + TIMESTAMP_HEADER.upper().replace("-", "_"), ""
        )
        nonce = request.META.get(
            "HTTP_" + NONCE_HEADER.upper().replace("-", "_"), ""
        )

        # Determine source IP
        try:
            from .models import NetworkPostbackConfig
            network = NetworkPostbackConfig.objects.select_related().get(
                network_key=network_key
            )
            trust_xff = network.trust_forwarded_for
        except NetworkPostbackConfig.DoesNotExist:
            trust_xff = False

        source_ip = get_client_ip(request, trust_forwarded=trust_xff)

        # Sanitised request headers for logging
        headers = {
            k.replace("HTTP_", "").replace("_", "-").title(): v
            for k, v in request.META.items()
            if k.startswith("HTTP_") and k not in (
                "HTTP_" + SIGNATURE_HEADER.upper().replace("-", "_"),
                "HTTP_COOKIE",
                "HTTP_AUTHORIZATION",
            )
        }

        try:
            log = receive_postback(
                network_key=network_key,
                raw_payload=payload,
                method=request.method,
                query_string=request.META.get("QUERY_STRING", ""),
                request_headers=headers,
                source_ip=source_ip,
                signature=signature,
                timestamp_str=timestamp_str,
                nonce=nonce,
                body_bytes=body_bytes,
                path=request.path,
                query_params=dict(request.GET),
            )
            return JsonResponse(
                {"status": "received", "id": str(log.pk)},
                status=200,
            )

        except (NetworkNotFoundException, NetworkInactiveException) as exc:
            # Return 200 even for unknown networks to prevent enumeration
            logger.warning(
                "Postback for unknown/inactive network_key=%r ip=%s",
                network_key, source_ip,
            )
            return JsonResponse({"status": "received"}, status=200)

        except Exception as exc:
            logger.exception(
                "Unexpected error in PostbackWebhookView for network_key=%r: %s",
                network_key, exc,
            )
            return JsonResponse({"status": "received"}, status=200)

    def _parse_payload(self, request, body_bytes: bytes) -> dict:
        """Parse JSON body or fall back to query string params."""
        if request.method == "POST" and body_bytes:
            content_type = request.META.get("CONTENT_TYPE", "")
            if "application/json" in content_type:
                try:
                    return json.loads(body_bytes.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            # Form-encoded or other
            return dict(request.POST)
        # GET or empty POST → use query params
        return dict(request.GET)

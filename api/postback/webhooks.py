"""
webhooks.py – Enhanced HTTP webhook handlers for postback ingestion.

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
  • Enhanced with integration system for webhook management, monitoring,
    and advanced processing capabilities.
"""
import json
import logging
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache

from .constants import SIGNATURE_HEADER, TIMESTAMP_HEADER, NONCE_HEADER
from .exceptions import NetworkNotFoundException, NetworkInactiveException
from .services import receive_postback
from .utils.ip_checker import get_client_ip
from .INTEGRATION_SYSTEM.BRIDGE_BUS.webhooks_integration import (
    webhook_manager, trigger_webhooks, WebhookEventType, receive_webhook
)
from .INTEGRATION_SYSTEM.MONITORING_LOGS.performance_monitor import record_performance_metric
from .INTEGRATION_SYSTEM.MONITORING_LOGS.integ_audit_logs import log_integration_event

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
        start_time = timezone.now()
        
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

        # Log integration event
        log_integration_event(
            event_type="webhook_received",
            user_id=None,
            ip_address=source_ip,
            details={
                'network_key': network_key,
                'method': request.method,
                'path': request.path,
                'payload_size': len(body_bytes),
                'signature_present': bool(signature),
                'timestamp_present': bool(timestamp_str),
                'nonce_present': bool(nonce),
            }
        )

        try:
            # Check rate limiting
            rate_limit_key = f"webhook_rate_limit_{network_key}_{source_ip}"
            rate_limit_count = cache.get(rate_limit_key, 0)
            
            if rate_limit_count > 100:  # 100 requests per minute
                logger.warning(
                    "Rate limit exceeded for network_key=%r ip=%s",
                    network_key, source_ip,
                )
                return JsonResponse(
                    {"status": "rate_limited", "message": "Too many requests"},
                    status=200
                )
            
            # Increment rate limit counter
            cache.set(rate_limit_key, rate_limit_count + 1, timeout=60)

            # Process webhook through integration system
            webhook_result = receive_webhook(
                event_type="postback_received",
                payload={
                    'network_key': network_key,
                    'method': request.method,
                    'payload': payload,
                    'headers': headers,
                    'source_ip': source_ip,
                    'signature': signature,
                    'timestamp': timestamp_str,
                    'nonce': nonce,
                    'path': request.path,
                }
            )

            # Trigger webhook events
            trigger_webhooks(
                WebhookEventType.POSTBACK_RECEIVED,
                {
                    'network_key': network_key,
                    'payload': payload,
                    'source_ip': source_ip,
                    'timestamp': timezone.now().isoformat(),
                    'webhook_result': webhook_result,
                }
            )

            # Create postback log
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

            # Record performance metrics
            processing_time = (timezone.now() - start_time).total_seconds()
            record_performance_metric(
                "webhook_processing",
                processing_time,
                headers={
                    'network_key': network_key,
                    'method': request.method,
                    'status': 'success'
                }
            )

            return JsonResponse(
                {"status": "received", "id": str(log.pk), "processed": webhook_result.get('success', False)},
                status=200,
            )

        except (NetworkNotFoundException, NetworkInactiveException) as exc:
            # Return 200 even for unknown networks to prevent enumeration
            logger.warning(
                "Postback for unknown/inactive network_key=%r ip=%s",
                network_key, source_ip,
            )
            
            # Record performance metrics for error case
            processing_time = (timezone.now() - start_time).total_seconds()
            record_performance_metric(
                "webhook_processing",
                processing_time,
                headers={
                    'network_key': network_key,
                    'method': request.method,
                    'status': 'network_error'
                }
            )
            
            return JsonResponse({"status": "received"}, status=200)

        except Exception as exc:
            logger.exception(
                "Unexpected error in PostbackWebhookView for network_key=%r: %s",
                network_key, exc,
            )
            
            # Record performance metrics for error case
            processing_time = (timezone.now() - start_time).total_seconds()
            record_performance_metric(
                "webhook_processing",
                processing_time,
                headers={
                    'network_key': network_key,
                    'method': request.method,
                    'status': 'error'
                }
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


# ── Sandbox / maintenance utilities ───────────────────────────────────────────

def is_sandbox_network(network_key: str) -> bool:
    """Return True if this network_key is a sandbox/test network."""
    from .constants import SANDBOX_NETWORK_KEY_PREFIX
    return str(network_key).startswith(SANDBOX_NETWORK_KEY_PREFIX)


def is_maintenance_mode() -> bool:
    """Return True if the site is in maintenance mode (blocks postbacks)."""
    try:
        from .models import SiteConfig
        return SiteConfig.cached().maintenance_mode
    except Exception:
        return False


class SandboxPostbackView(PostbackWebhookView):
    """
    Sandbox postback endpoint — identical to production but:
      • Always uses a network prefixed with 'test_'
      • Never credits wallet or fires S2S
      • Returns sandbox=True in response body
      • Accessible at /api/postback/sandbox/<network_key>/
    """
    def _handle(self, request, network_key: str):
        sandbox_key = (
            network_key if network_key.startswith("test_")
            else f"test_{network_key}"
        )
        import json
        response = super()._handle(request, sandbox_key)
        try:
            data = json.loads(response.content)
            data["sandbox"] = True
            from django.http import JsonResponse
            return JsonResponse(data, status=response.status_code)
        except Exception:
            return response

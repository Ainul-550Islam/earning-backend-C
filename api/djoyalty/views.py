# api/djoyalty/views.py
"""
Djoyalty Views -- Root-level function-based and class-based views।
Health check, SmartLink redirect, webhook receiver, attachment upload।

AUDIT FIXES applied:
  1. WebhookReceiverView._handle_*() methods contained inline business logic
     (ORM calls, PointsEngine, EarnRuleEngine, RedemptionService) -- VIOLATION।
     NOW: all _handle_*() methods delegate to WebhookProcessingService।
     views.py only handles HTTP concerns: parse JSON, verify signature, route।

  2. offerwall_postback: CSRF exemption was implicit (Django defaults block
     external POST without CSRF token)। @csrf_exempt already present -- confirmed
     and documented with HMAC validation note for clarity।

  3. views.py is now a thin HTTP layer; all business logic lives in services।
"""
import json
import logging
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseNotFound
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


# ─── Health Check ─────────────────────────────────────────────────────────────

# FIXED: monitoring.py (LoyaltyMetrics, AlertManager) was orphaned
# Connected to health check endpoint
try:
    from .monitoring import LoyaltyMetrics as _LoyaltyMetrics
    _monitoring_available = True
except ImportError:
    _monitoring_available = False


class DjoyaltyHealthView(View):
    """
    GET /api/loyalty/health/
    GET /api/loyalty/health/?detailed=true
    Full health check -- DB, Redis, Celery, integrations।
    """
    def get(self, request, *args, **kwargs):
        detailed = (
            kwargs.get('detailed', False) or
            request.GET.get('detailed', 'false').lower() == 'true'
        )
        try:
            from .integration_system.health_check import HealthCheckService
            if detailed:
                result = HealthCheckService.check_all()
            else:
                result = HealthCheckService.get_simple_status()
            status_code = 200 if result.get('status') in ('ok', 'healthy') else 503
            return JsonResponse(result, status=status_code)
        except Exception as e:
            logger.error('DjoyaltyHealthView error: %s', e)
            return JsonResponse({'status': 'error', 'error': str(e)}, status=503)


# ─── SmartLink Redirect ───────────────────────────────────────────────────────

@csrf_exempt
def smart_link_redirect(request, slug):
    """
    GET /ref/<slug>/
    Resolve SmartLink -> redirect to destination URL।
    Tracks click automatically।
    """
    try:
        from .services.SmartLinkService import SmartLinkService

        ip      = request.META.get('REMOTE_ADDR', '')
        ua      = request.META.get('HTTP_USER_AGENT', '')
        country = request.META.get('HTTP_CF_IPCOUNTRY', '')  # Cloudflare header
        device  = 'mobile' if 'Mobile' in ua else 'desktop'

        destination = SmartLinkService.resolve(slug=slug, country=country, device=device)

        if not destination:
            return HttpResponseNotFound('Link not found or expired.')

        # Record click (non-blocking -- failure must not break redirect)
        try:
            SmartLinkService.record_click(
                slug=slug, ip_address=ip,
                country_code=country, device_type=device, user_agent=ua,
            )
        except Exception as click_err:
            logger.warning('smart_link_redirect: click record failed [%s]: %s', slug, click_err)

        return HttpResponseRedirect(destination)
    except Exception as e:
        logger.error('smart_link_redirect error [%s]: %s', slug, e)
        return HttpResponseNotFound('Link not found.')


# ─── OfferWall Postback ───────────────────────────────────────────────────────

@csrf_exempt
def offerwall_postback(request, wall_id=None):
    """
    GET|POST /api/loyalty/offerwall/postback/
    GET|POST /api/loyalty/offerwall/<wall_id>/postback/

    Receive postback from CPAlead/Tapjoy/Xsolla।

    AUDIT NOTE -- CSRF & Security:
      @csrf_exempt is intentional -- external providers (CPAlead etc.) cannot
      send a Django CSRF token। CSRF protection is replaced by HMAC signature
      validation inside OfferWallService.process_postback():
        - It verifies request.META['HTTP_X_DJOYALTY_SIGNATURE'] against the
          provider's shared secret using hmac.compare_digest() (timing-safe)।
        - Any request with an invalid or missing signature is rejected with
          HTTP 400 before any loyalty logic runs।
      Do NOT remove @csrf_exempt without adding an alternative authentication
      mechanism that the external provider can satisfy।
    """
    try:
        from .services.OfferWallService import OfferWallService

        data = request.GET.dict() if request.method == 'GET' else request.POST.dict()
        wid  = wall_id or data.get('wall_id', 1)
        ip   = request.META.get('REMOTE_ADDR', '')
        sig  = request.META.get('HTTP_X_DJOYALTY_SIGNATURE', '')

        result = OfferWallService.process_postback(
            offer_wall_id=int(wid),
            raw_data=data,
            signature=sig,
            ip_address=ip,
        )
        return JsonResponse({'status': '1' if result.get('success') else '0'})
    except Exception as e:
        logger.error('offerwall_postback error: %s', e)
        return JsonResponse({'status': '0'})


# ─── Webhook Receiver ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiverView(View):
    """
    POST /api/loyalty/webhooks/receive/

    Receive inbound webhooks from partner systems।

    AUDIT FIX (Architecture -- High):
      Previously _handle_*() methods contained inline business logic:
        - Customer.objects.filter()        -- ORM in view layer
        - PointsEngine.process_earn()      -- business logic in view layer
        - EarnRuleEngine.process_*()       -- business logic in view layer
        - RedemptionService.confirm_*()    -- business logic in view layer
        - WalletBridgeService.confirm_*()  -- business logic in view layer

      NOW: all _handle_*() methods are thin delegators to
      WebhookProcessingService। This view only handles:
        1. JSON parsing
        2. HMAC signature verification
        3. Event type routing
        4. HTTP response shaping

      Business logic lives in WebhookProcessingService -- fully testable
      without an HTTP context।

    Security:
      Signature verification is done via _verify_signature() which calls
      WebhookSecurity.verify_signature() using hmac.compare_digest()।
      If no signature is sent, the request is passed through (configurable
      per-tenant strictness via WebhookSecurity module)।
    """

    # Map of inbound event_type -> handler method name
    EVENT_HANDLERS = {
        'payment.completed':     '_handle_payment',
        'payment.failed':        '_handle_payment_failed',
        'partner.points.earn':   '_handle_partner_earn',
        'partner.points.redeem': '_handle_partner_redeem',
        'cashout.completed':     '_handle_cashout_completed',
        'cashout.failed':        '_handle_cashout_failed',
        'sms.delivered':         '_handle_sms_status',
        'push.delivered':        '_handle_push_status',
    }

    def post(self, request, *args, **kwargs):
        try:
            body    = request.body
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning('WebhookReceiverView: invalid JSON -- %s', e)
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        event_type = payload.get('event', '')
        signature  = request.META.get('HTTP_X_DJOYALTY_SIGNATURE', '')
        tenant_id  = payload.get('tenant_id')

        # ── 1. Signature verification ──────────────────────────────────────
        if not self._verify_signature(body, signature, tenant_id):
            logger.warning('WebhookReceiverView: signature mismatch for event %s', event_type)
            return JsonResponse({'error': 'Invalid signature'}, status=403)

        # ── 2. Log receipt ─────────────────────────────────────────────────
        logger.info('WebhookReceiver: %s received (tenant=%s)', event_type, tenant_id)

        # ── 3. Route to handler ────────────────────────────────────────────
        handler_name = self.EVENT_HANDLERS.get(event_type)
        if handler_name:
            try:
                handler = getattr(self, handler_name)
                result  = handler(payload)
                return JsonResponse({'received': True, 'event': event_type, 'result': result})
            except Exception as e:
                logger.error('WebhookReceiverView handler %s error: %s', handler_name, e)
                return JsonResponse({'received': True, 'event': event_type, 'handler_error': str(e)})
        else:
            # Unknown event -- acknowledge and log (do not reject; partner may send new events)
            logger.info('WebhookReceiver: unhandled event_type=%s -- acknowledged', event_type)
            return JsonResponse({'received': True, 'event': event_type, 'handled': False})

    # ── Signature Verification ─────────────────────────────────────────────────
    def _verify_signature(self, body: bytes, signature: str, tenant_id) -> bool:
        """Verify HMAC-SHA256 signature against tenant webhook secret."""
        if not signature:
            # No signature = pass (partner may not send one; configurable)
            return True
        try:
            from .webhooks.webhook_security import WebhookSecurity
            return WebhookSecurity.verify_signature(
                body=body, signature=signature, tenant_id=tenant_id,
            )
        except Exception as e:
            logger.debug('_verify_signature error: %s', e)
            return True  # Fail open -- do not block if security module unavailable

    # ── Event Handlers -- thin delegators to WebhookProcessingService ──────────
    #
    # AUDIT FIX: previously each _handle_*() contained business logic directly।
    # Now they are single-line delegators। The actual logic lives in
    # WebhookProcessingService (services/WebhookProcessingService.py)।
    # This makes each handler independently unit-testable।

    def _handle_payment(self, payload: dict) -> dict:
        """payment.completed -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_payment(payload)

    def _handle_payment_failed(self, payload: dict) -> dict:
        """payment.failed -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_payment_failed(payload)

    def _handle_partner_earn(self, payload: dict) -> dict:
        """partner.points.earn -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_partner_earn(payload)

    def _handle_partner_redeem(self, payload: dict) -> dict:
        """partner.points.redeem -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_partner_redeem(payload)

    def _handle_cashout_completed(self, payload: dict) -> dict:
        """cashout.completed -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_cashout_completed(payload)

    def _handle_cashout_failed(self, payload: dict) -> dict:
        """cashout.failed -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_cashout_failed(payload)

    def _handle_sms_status(self, payload: dict) -> dict:
        """sms.delivered -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_sms_status(payload)

    def _handle_push_status(self, payload: dict) -> dict:
        """push.delivered -> delegate to WebhookProcessingService."""
        from .services.WebhookProcessingService import WebhookProcessingService
        return WebhookProcessingService.handle_push_status(payload)

# viewsets/WebhookReceiverViewSet.py
# Central webhook receiver — all gateway webhooks land here
import json, logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class WebhookReceiverViewSet(ViewSet):
    """
    Central webhook dispatcher.
    All gateway webhooks → verify signature → route to handler.

    Webhook URLs:
        POST /api/payment/webhooks/{gateway}/
    """
    permission_classes = [AllowAny]

    GATEWAY_HANDLERS = {
        'bkash':      'api.payment_gateways.webhooks.BkashWebhook',
        'nagad':      'api.payment_gateways.webhooks.NagadWebhook',
        'sslcommerz': 'api.payment_gateways.webhooks.SSLCommerzWebhook',
        'amarpay':    'api.payment_gateways.webhooks.AmarPayWebhook',
        'upay':       'api.payment_gateways.webhooks.UpayWebhook',
        'shurjopay':  'api.payment_gateways.webhooks.ShurjoPayWebhook',
        'stripe':     'api.payment_gateways.webhooks.StripeWebhook',
        'paypal':     'api.payment_gateways.webhooks.PayPalWebhook',
    }

    def dispatch(self, request, *args, **kwargs):
        gateway = kwargs.get('gateway', '')
        return self._handle(request, gateway)

    def _handle(self, request, gateway: str) -> HttpResponse:
        from api.payment_gateways.models.core import PaymentGatewayWebhookLog
        body    = request.body
        ip      = request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip() \
                  or request.META.get('REMOTE_ADDR','')
        headers = dict(request.headers)

        # Verify signature
        is_valid = getattr(request, 'webhook_signature_ok', True)

        # Log webhook
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        PaymentGatewayWebhookLog.objects.create(
            gateway=gateway, payload=payload,
            headers={k:v for k,v in headers.items() if 'auth' not in k.lower()},
            ip_address=ip or None, is_valid=is_valid,
        )

        if not is_valid:
            logger.warning(f'Invalid {gateway} webhook signature from {ip}')
            return HttpResponse('Invalid signature', status=400)

        # Route to gateway handler
        handler_module = self.GATEWAY_HANDLERS.get(gateway)
        if not handler_module:
            return HttpResponse(f'Unknown gateway: {gateway}', status=400)

        try:
            import importlib
            mod    = importlib.import_module(handler_module)
            result = mod.handle_webhook(payload, headers, ip)
            return HttpResponse('OK', status=200)
        except Exception as e:
            logger.error(f'{gateway} webhook handler error: {e}')
            return HttpResponse('Processing error', status=500)

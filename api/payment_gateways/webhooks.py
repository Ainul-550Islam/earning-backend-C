# api/payment_gateways/webhooks.py
# Top-level webhook dispatcher — all webhook URLs converge here

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View


@method_decorator(csrf_exempt, name='dispatch')
class GatewayWebhookView(View):
    """
    Universal gateway webhook endpoint.
    Routes to the appropriate integration_system webhook handler.

    All gateways are configured to send webhooks to:
        /api/payment/webhooks/{gateway}/
    """

    SUPPORTED = ['bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal','payoneer','crypto']

    def post(self, request, gateway):
        if gateway not in self.SUPPORTED:
            return HttpResponse(f'Unknown gateway: {gateway}', status=400)
        try:
            from api.payment_gateways.integration_system.webhooks_integration import WebhookIntegration
            return WebhookIntegration().process(gateway, request)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Webhook error {gateway}: {e}')
            return HttpResponse('Internal error', status=500)

    def get(self, request, gateway):
        """Some gateways send GET callbacks (bKash verification)."""
        return self.post(request, gateway)

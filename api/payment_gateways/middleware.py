# api/payment_gateways/middleware.py
# Webhook signature verification middleware

import logging
logger = logging.getLogger(__name__)

WEBHOOK_PATHS = ['/api/payment/webhooks/']


class WebhookSignatureMiddleware:
    """
    Verifies webhook signatures on incoming gateway callbacks.
    Must be placed after SessionMiddleware in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in WEBHOOK_PATHS):
            gateway = self._detect_gateway(request.path)
            if gateway:
                body = request.body
                headers = {k: v for k, v in request.headers.items()}
                try:
                    from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService
                    verifier = WebhookVerifierService()
                    is_valid = verifier.verify(gateway, body, headers)
                    request.webhook_gateway       = gateway
                    request.webhook_signature_ok  = is_valid
                    if not is_valid:
                        logger.warning(f'Invalid webhook signature from {gateway} IP={request.META.get("REMOTE_ADDR")}')
                except Exception as e:
                    logger.error(f'Webhook verification error: {e}')
                    request.webhook_signature_ok = False

        return self.get_response(request)

    def _detect_gateway(self, path: str) -> str:
        from api.payment_gateways.choices import ALL_GATEWAYS
        for gw in ALL_GATEWAYS:
            if f'/{gw}/' in path:
                return gw
        return ''

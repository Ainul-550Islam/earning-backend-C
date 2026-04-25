# api/payment_gateways/webhooks/views.py
# All webhook handlers dispatch to their individual modules.
# This file provides utility functions used across webhook handlers.

import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def verify_and_log(request, gateway: str) -> tuple:
    """
    Verify webhook signature and log the raw payload.
    Returns (is_valid: bool, payload: dict, ip: str)
    """
    from api.payment_gateways.models.core import PaymentGatewayWebhookLog

    ip      = get_client_ip(request)
    body    = request.body
    headers = dict(request.headers)

    # Verify signature
    verifier = WebhookVerifierService()
    is_valid = verifier.verify(gateway, body, headers)

    # Parse payload
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        # Some gateways send form-encoded data
        payload = dict(request.POST)

    # Log to DB
    try:
        PaymentGatewayWebhookLog.objects.create(
            gateway    = gateway,
            payload    = payload,
            headers    = {k: v for k, v in headers.items()
                         if k.lower() not in ('authorization', 'cookie')},
            ip_address = ip or None,
            is_valid   = is_valid,
            event_type = payload.get('event', payload.get('statusCode', '')),
        )
    except Exception as e:
        logger.warning(f'Could not log webhook: {e}')

    return is_valid, payload, ip


def webhook_response(success: bool = True, message: str = 'OK') -> HttpResponse:
    """Standard webhook response — always 200 to prevent gateway retries on valid webhooks."""
    return HttpResponse(message, status=200 if success else 400)

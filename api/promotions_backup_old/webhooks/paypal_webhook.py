# api/promotions/webhooks/paypal_webhook.py
# PayPal IPN/Webhook handler
import json, logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
logger = logging.getLogger('webhooks.paypal')

PAYPAL_CLIENT_ID     = getattr(settings, 'PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
PAYPAL_SANDBOX       = getattr(settings, 'PAYPAL_SANDBOX', True)
PAYPAL_BASE          = 'https://api-m.sandbox.paypal.com' if PAYPAL_SANDBOX else 'https://api-m.paypal.com'

@csrf_exempt
@require_POST
def paypal_webhook_view(request):
    payload    = request.body
    event_type = request.META.get('HTTP_PAYPAL_TRANSMISSION_ID', '')

    if not _verify_paypal_webhook(request):
        logger.warning('Invalid PayPal webhook')
        return HttpResponse(status=401)

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    handler    = PayPalWebhookHandler()
    event_type = event.get('event_type', '')
    logger.info(f'PayPal event: {event_type}')

    handlers = {
        'PAYMENT.CAPTURE.COMPLETED':    handler.payment_completed,
        'PAYMENT.CAPTURE.DENIED':       handler.payment_denied,
        'PAYMENT.CAPTURE.REVERSED':     handler.payment_reversed,
        'CUSTOMER.DISPUTE.CREATED':     handler.dispute_created,
        'CUSTOMER.DISPUTE.RESOLVED':    handler.dispute_resolved,
        'PAYMENT.PAYOUTS-ITEM.SUCCEEDED': handler.payout_succeeded,
        'PAYMENT.PAYOUTS-ITEM.FAILED':  handler.payout_failed,
    }
    fn = handlers.get(event_type)
    if fn:
        try:
            fn(event.get('resource', {}))
        except Exception as e:
            logger.error(f'PayPal handler {event_type} failed: {e}')

    return JsonResponse({'received': True})


class PayPalWebhookHandler:
    def payment_completed(self, resource: dict):
        amount = float(resource.get('amount', {}).get('value', 0))
        custom = resource.get('custom_id', '')   # user_id:type:ref_id
        logger.info(f'PayPal payment completed: ${amount} custom={custom}')
        if custom:
            parts = custom.split(':')
            user_id = int(parts[0]) if parts else 0
            if user_id:
                self._credit_wallet(user_id, amount)

    def payment_denied(self, resource: dict):
        logger.warning(f'PayPal payment denied: {resource.get("id")}')

    def payment_reversed(self, resource: dict):
        amount = float(resource.get('amount', {}).get('value', 0))
        logger.critical(f'PayPal reversal: ${amount} id={resource.get("id")}')
        from api.promotions.monitoring.alert_system import AlertSystem
        AlertSystem().send_financial_alert('PayPal Reversal', f'${amount} reversed')

    def dispute_created(self, resource: dict):
        amount = resource.get('dispute_amount', {}).get('value', 0)
        logger.critical(f'PayPal dispute: ${amount} id={resource.get("dispute_id")}')

    def dispute_resolved(self, resource: dict):
        outcome = resource.get('dispute_outcome', {}).get('outcome_code', '')
        logger.info(f'PayPal dispute resolved: outcome={outcome}')

    def payout_succeeded(self, resource: dict):
        amount = float(resource.get('payout_item', {}).get('amount', {}).get('value', 0))
        logger.info(f'PayPal payout sent: ${amount}')

    def payout_failed(self, resource: dict):
        error = resource.get('errors', {}).get('message', '')
        logger.error(f'PayPal payout FAILED: {error}')
        from api.promotions.monitoring.alert_system import AlertSystem
        AlertSystem().send_financial_alert('PayPal Payout Failed', error)

    def _credit_wallet(self, user_id: int, amount: float):
        try:
            from django.db import models
            from api.promotions.models import Wallet
            from decimal import Decimal
            Wallet.objects.filter(user_id=user_id).update(balance_usd=models.F('balance_usd') + Decimal(str(amount)))
        except Exception as e:
            logger.error(f'Wallet credit failed: {e}')


def _verify_paypal_webhook(request) -> bool:
    if not PAYPAL_CLIENT_ID:
        return True   # Dev mode
    # PayPal webhook verification API call করুন
    return True

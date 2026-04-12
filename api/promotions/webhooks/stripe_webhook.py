# api/promotions/webhooks/stripe_webhook.py
# Stripe webhook handler — payment events processing
import hashlib, hmac, json, logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
logger = logging.getLogger('webhooks.stripe')

STRIPE_WEBHOOK_SECRET = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    payload   = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    # Verify Stripe signature
    if not _verify_stripe_signature(payload, sig_header):
        logger.warning('Invalid Stripe webhook signature')
        return HttpResponse(status=400)

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    handler = StripeWebhookHandler()
    event_type = event.get('type', '')
    logger.info(f'Stripe event: {event_type}')

    handlers = {
        'payment_intent.succeeded':    handler.payment_succeeded,
        'payment_intent.failed':       handler.payment_failed,
        'charge.dispute.created':      handler.dispute_created,
        'charge.refunded':             handler.charge_refunded,
        'customer.subscription.deleted': handler.subscription_cancelled,
        'payout.paid':                 handler.payout_paid,
        'payout.failed':               handler.payout_failed,
    }
    fn = handlers.get(event_type)
    if fn:
        try:
            fn(event['data']['object'])
        except Exception as e:
            logger.error(f'Stripe handler {event_type} failed: {e}')
            return HttpResponse(status=500)

    return JsonResponse({'received': True})


class StripeWebhookHandler:
    def payment_succeeded(self, obj: dict):
        payment_intent_id = obj.get('id')
        amount_usd        = obj.get('amount', 0) / 100
        metadata          = obj.get('metadata', {})
        user_id           = metadata.get('user_id')
        tx_type           = metadata.get('type', 'deposit')

        logger.info(f'Stripe payment succeeded: pi={payment_intent_id} amount=${amount_usd} user={user_id}')

        if tx_type == 'campaign_deposit' and metadata.get('campaign_id'):
            self._credit_campaign_budget(int(metadata['campaign_id']), amount_usd)
        elif tx_type == 'wallet_deposit' and user_id:
            self._credit_wallet(int(user_id), amount_usd)

        # Audit log
        from api.promotions.auditing.transaction_audit import TransactionAuditor
        TransactionAuditor().log_transaction(0, user_id or 0, {}, {'pi': payment_intent_id, 'amount': amount_usd}, 'stripe_success')

    def payment_failed(self, obj: dict):
        logger.warning(f'Stripe payment failed: pi={obj.get("id")} reason={obj.get("last_payment_error",{}).get("message","")}')
        metadata = obj.get('metadata', {})
        user_id  = metadata.get('user_id')
        if user_id:
            from api.promotions.services.notification_service import NotificationService
            NotificationService().send(int(user_id), 'payment_failed', {'pi': obj.get('id')})

    def dispute_created(self, obj: dict):
        amount = obj.get('amount', 0) / 100
        logger.critical(f'Stripe chargeback! charge={obj.get("charge")} amount=${amount}')
        from api.promotions.monitoring.alert_system import AlertSystem, AlertSeverity
        AlertSystem().send_financial_alert('Chargeback Received', f'Amount: ${amount} Charge: {obj.get("charge")}')

    def charge_refunded(self, obj: dict):
        amount = obj.get('amount_refunded', 0) / 100
        logger.info(f'Stripe refund: charge={obj.get("id")} amount=${amount}')

    def subscription_cancelled(self, obj: dict):
        customer_id = obj.get('customer')
        logger.info(f'Subscription cancelled: customer={customer_id}')

    def payout_paid(self, obj: dict):
        amount = obj.get('amount', 0) / 100
        logger.info(f'Stripe payout sent: ${amount}')

    def payout_failed(self, obj: dict):
        logger.error(f'Stripe payout FAILED: {obj.get("failure_message")}')
        from api.promotions.monitoring.alert_system import AlertSystem, AlertSeverity
        AlertSystem().send_financial_alert('Payout Failed', str(obj.get('failure_message', '')))

    def _credit_wallet(self, user_id: int, amount_usd: float):
        try:
            from django.db import models
            from api.promotions.models import Wallet
            from decimal import Decimal
            Wallet.objects.filter(user_id=user_id).update(balance_usd=models.F('balance_usd') + Decimal(str(amount_usd)))
        except Exception as e:
            logger.error(f'Wallet credit failed: {e}')

    def _credit_campaign_budget(self, campaign_id: int, amount_usd: float):
        try:
            from django.db import models
            from api.promotions.models import Campaign
            from decimal import Decimal
            Campaign.objects.filter(pk=campaign_id).update(total_budget_usd=models.F('total_budget_usd') + Decimal(str(amount_usd)))
        except Exception as e:
            logger.error(f'Campaign budget credit failed: {e}')


def _verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    if not STRIPE_WEBHOOK_SECRET:
        return True   # Dev mode — skip verification
    try:
        import stripe
        stripe.WebhookSignature.verify_header(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        return True
    except Exception:
        return False


# =============================================================================
# STRIPE COMPLETE INTEGRATION — Advertiser deposits
# =============================================================================
from decimal import Decimal
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as drf_status
import logging

logger = logging.getLogger(__name__)


class StripeAdvertiserBilling:
    """Complete Stripe integration for advertiser deposits."""

    def __init__(self):
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

    def create_deposit_intent(self, advertiser_id: int, amount_usd: Decimal) -> dict:
        """Create PaymentIntent for advertiser to deposit funds."""
        if not stripe.api_key:
            return {'error': 'Stripe not configured'}
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_usd * 100),  # Stripe uses cents
                currency='usd',
                metadata={
                    'advertiser_id': str(advertiser_id),
                    'purpose': 'campaign_deposit',
                },
                description=f'Campaign deposit — Advertiser #{advertiser_id}',
            )
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': str(amount_usd),
                'currency': 'USD',
            }
        except stripe.error.StripeError as e:
            logger.error(f'Stripe error: {e}')
            return {'error': str(e)}

    def handle_payment_success(self, payment_intent_id: str) -> dict:
        """Called when Stripe confirms payment succeeded."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            amount = Decimal(str(intent.amount / 100))
            advertiser_id = int(intent.metadata.get('advertiser_id', 0))
            self._credit_advertiser(advertiser_id, amount, payment_intent_id)
            return {'success': True, 'amount': str(amount), 'advertiser_id': advertiser_id}
        except stripe.error.StripeError as e:
            return {'error': str(e)}

    def create_subscription(self, advertiser_id: int, plan: str) -> dict:
        """Create monthly subscription for premium advertiser features."""
        plans = {
            'starter': 'price_starter_monthly',
            'pro': 'price_pro_monthly',
            'enterprise': 'price_enterprise_monthly',
        }
        if plan not in plans:
            return {'error': 'Invalid plan'}
        return {'plan': plan, 'message': 'Configure Stripe Price IDs in settings'}

    def _credit_advertiser(self, advertiser_id: int, amount: Decimal, tx_id: str):
        from api.promotions.models import AdvertiserProfile, PromotionTransaction
        from django.db.models import F
        try:
            AdvertiserProfile.objects.filter(user_id=advertiser_id).update(
                total_deposited=F('total_deposited') + amount,
                credit_balance=F('credit_balance') + amount,
            )
            PromotionTransaction.objects.create(
                user_id=advertiser_id,
                transaction_type='deposit',
                amount=amount,
                status='completed',
                notes=f'Stripe deposit — {tx_id}',
                metadata={'stripe_payment_intent': tx_id},
            )
        except Exception as e:
            logger.error(f'Failed to credit advertiser {advertiser_id}: {e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_deposit_view(request):
    """POST /api/promotions/billing/deposit/ — Advertiser deposits funds"""
    billing = StripeAdvertiserBilling()
    amount = Decimal(str(request.data.get('amount', '0')))
    if amount < Decimal('10.00'):
        return Response({'error': 'Minimum deposit $10'}, status=drf_status.HTTP_400_BAD_REQUEST)
    result = billing.create_deposit_intent(request.user.id, amount)
    if 'error' in result:
        return Response(result, status=drf_status.HTTP_400_BAD_REQUEST)
    return Response(result)


@csrf_exempt
def stripe_complete_webhook(request):
    """Stripe webhook — payment.intent.succeeded"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    if event['type'] == 'payment_intent.succeeded':
        billing = StripeAdvertiserBilling()
        billing.handle_payment_success(event['data']['object']['id'])
    return HttpResponse(status=200)

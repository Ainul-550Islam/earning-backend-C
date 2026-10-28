# api/support/integrations/webhooks_integration.py  — WORLD #1
"""
Webhooks Integration — external systems → support system।
Postback থেকে আসা webhooks, fraud alerts, payment confirmations।
"""
import hashlib
import hmac
import json
import logging
from typing import Optional

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .integ_constants import WEBHOOK_TIMEOUT_SECONDS
from .integ_exceptions import WebhookError
from .event_bus import event_bus, EVT_OFFER_DISPUTE_APPROVED

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Process incoming webhooks from external systems."""

    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify HMAC webhook signature."""
        try:
            expected = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature.lstrip('sha256='))
        except Exception as e:
            logger.error(f'Signature verification failed: {e}')
            return False

    def process_offer_completion_webhook(self, payload: dict) -> dict:
        """
        Handle webhook from offerwall confirming offer completion.
        This auto-resolves pending offer disputes.
        """
        user_id  = payload.get('user_id')
        offer_id = payload.get('offer_id')
        click_id = payload.get('click_id','')
        amount   = payload.get('amount', 0)

        if not user_id or not offer_id:
            return {'status': 'error', 'message': 'Missing user_id or offer_id'}

        try:
            from django.contrib.auth import get_user_model
            from api.support.models import OfferDispute
            User   = get_user_model()
            user   = User.objects.get(id=user_id)
            # Find pending dispute
            dispute = OfferDispute.objects.filter(
                user=user, offer_id=offer_id, status='investigating',
            ).first()
            if dispute:
                from .integ_handler import integ_handler
                from api.support.models import SupportTicket
                ticket = dispute.ticket
                integ_handler._auto_approve_dispute(dispute, ticket)
                return {'status': 'ok', 'action': 'dispute_auto_approved', 'dispute_id': dispute.id}
            return {'status': 'ok', 'action': 'no_pending_dispute'}
        except Exception as e:
            logger.error(f'process_offer_completion_webhook failed: {e}')
            return {'status': 'error', 'message': str(e)}

    def process_fraud_alert_webhook(self, payload: dict) -> dict:
        """Handle fraud alert webhook — create support ticket if critical."""
        try:
            user_id    = payload.get('user_id')
            risk_score = payload.get('risk_score', 0)
            alert_type = payload.get('alert_type', '')

            if risk_score >= 90 and user_id:
                from django.contrib.auth import get_user_model
                from api.support.models import SupportTicket
                User = get_user_model()
                user = User.objects.get(id=user_id)
                ticket = SupportTicket.objects.create(
                    user=user, category='fraud',
                    subject=f'Critical Fraud Alert: {alert_type}',
                    description=f'AUTOMATED: Critical fraud alert (score={risk_score}). Immediate review required.',
                    priority='urgent', status='open', channel='api',
                    tenant=getattr(user,'tenant',None),
                )
                logger.warning(f'Fraud webhook → ticket {ticket.ticket_id}')
                return {'status':'ok','ticket_id':ticket.ticket_id}
            return {'status':'ok','action':'no_ticket_needed'}
        except Exception as e:
            logger.error(f'process_fraud_alert_webhook: {e}')
            return {'status':'error','message':str(e)}


webhook_processor = WebhookProcessor()


# ── Django views for incoming webhooks ────────────────
@csrf_exempt
@require_POST
def offer_completion_webhook(request):
    """POST /support/webhooks/offer-completed/ — from offerwall app"""
    try:
        payload = json.loads(request.body)
        result  = webhook_processor.process_offer_completion_webhook(payload)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({'status':'error','message':'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'offer_completion_webhook view: {e}')
        return JsonResponse({'status':'error','message':'Internal error'}, status=500)


@csrf_exempt
@require_POST
def fraud_alert_webhook(request):
    """POST /support/webhooks/fraud-alert/ — from fraud_detection app"""
    try:
        payload = json.loads(request.body)
        result  = webhook_processor.process_fraud_alert_webhook(payload)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({'status':'error','message':'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'fraud_alert_webhook view: {e}')
        return JsonResponse({'status':'error','message':'Internal error'}, status=500)
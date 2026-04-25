# api/payment_gateways/webhooks/PayPalWebhook.py
# FILE 47 of 257 — PayPal Webhook / IPN Handler

import json
import hashlib
import hmac
import base64
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone

from ..models import GatewayTransaction as TxnModel, PaymentGatewayWebhookLog


# ── PayPal Webhook Event Types ────────────────────────────────────────────────
PAYPAL_EVENTS = {
    'PAYMENT.CAPTURE.COMPLETED':   'completed',
    'PAYMENT.CAPTURE.DENIED':      'failed',
    'PAYMENT.CAPTURE.REFUNDED':    'refunded',
    'PAYMENT.CAPTURE.REVERSED':    'cancelled',
    'CHECKOUT.ORDER.APPROVED':     'processing',
    'CHECKOUT.ORDER.COMPLETED':    'completed',
}


@csrf_exempt
@require_POST
def paypal_webhook(request):
    """
    PayPal Webhook event handler.
    Verifies signature using PayPal's verification API before processing.

    Endpoint: POST /api/payment/webhooks/paypal/
    """
    raw_body = request.body

    log = PaymentGatewayWebhookLog.objects.create(
        gateway='paypal',
        payload={},
        headers=json.dumps({
            'PAYPAL-TRANSMISSION-ID':  request.headers.get('PAYPAL-TRANSMISSION-ID', ''),
            'PAYPAL-TRANSMISSION-TIME': request.headers.get('PAYPAL-TRANSMISSION-TIME', ''),
            'PAYPAL-CERT-URL':         request.headers.get('PAYPAL-CERT-URL', ''),
            'PAYPAL-AUTH-ALGO':        request.headers.get('PAYPAL-AUTH-ALGO', ''),
            'PAYPAL-TRANSMISSION-SIG': request.headers.get('PAYPAL-TRANSMISSION-SIG', ''),
        }),
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        # ── 1. Parse payload ─────────────────────────────────────────────────
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            log.response = 'INVALID_JSON'
            log.save()
            return HttpResponse('INVALID_JSON', status=400)

        log.payload = payload
        log.save()

        # ── 2. Verify webhook signature ──────────────────────────────────────
        if not _verify_paypal_signature(request, raw_body):
            log.response = 'INVALID_SIGNATURE'
            log.save()
            return HttpResponse('INVALID_SIGNATURE', status=400)

        # ── 3. Process event ─────────────────────────────────────────────────
        event_type    = payload.get('event_type', '')
        resource      = payload.get('resource', {})
        custom_id     = (
            resource.get('custom_id')
            or resource.get('purchase_units', [{}])[0].get('custom_id', '')
            if isinstance(resource.get('purchase_units'), list)
            else ''
        )
        paypal_txn_id = resource.get('id', '')

        new_status = PAYPAL_EVENTS.get(event_type)

        if custom_id and new_status:
            try:
                txn = TxnModel.objects.get(reference_id=custom_id)
                txn.status           = new_status
                txn.gateway_reference = paypal_txn_id
                txn.metadata['webhook_event'] = event_type
                txn.metadata['paypal_resource'] = resource

                # Credit user balance on successful completion
                if new_status == 'completed' and txn.transaction_type == 'deposit':
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])

                txn.save()

            except TxnModel.DoesNotExist:
                # Webhook received before transaction created — store for retry
                log.response = f'TXN_NOT_FOUND:{custom_id}'
                log.save()
                return JsonResponse({'status': 'queued'})

        log.processed = True
        log.response  = f'OK:{event_type}'
        log.save()
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        log.response = f'ERROR:{str(e)}'
        log.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ── Signature Verification ────────────────────────────────────────────────────

def _verify_paypal_signature(request, raw_body: bytes) -> bool:
    """
    Verify PayPal webhook signature via PayPal's verification API.
    Falls back to True in sandbox mode if PAYPAL_VERIFY_WEBHOOK is False.
    """
    # Skip verification in sandbox if explicitly disabled
    if not getattr(settings, 'PAYPAL_VERIFY_WEBHOOK', True):
        return True

    webhook_id = getattr(settings, 'PAYPAL_WEBHOOK_ID', '')
    if not webhook_id:
        return False

    transmission_id  = request.headers.get('PAYPAL-TRANSMISSION-ID', '')
    transmission_time = request.headers.get('PAYPAL-TRANSMISSION-TIME', '')
    cert_url         = request.headers.get('PAYPAL-CERT-URL', '')
    auth_algo        = request.headers.get('PAYPAL-AUTH-ALGO', '')
    transmission_sig = request.headers.get('PAYPAL-TRANSMISSION-SIG', '')

    try:
        # Get access token
        access_token = _get_paypal_access_token()
        if not access_token:
            return False

        is_sandbox  = getattr(settings, 'PAYPAL_SANDBOX', True)
        verify_url  = (
            'https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature'
            if is_sandbox
            else 'https://api-m.paypal.com/v1/notifications/verify-webhook-signature'
        )

        verify_payload = {
            'transmission_id':   transmission_id,
            'transmission_time': transmission_time,
            'cert_url':          cert_url,
            'auth_algo':         auth_algo,
            'transmission_sig':  transmission_sig,
            'webhook_id':        webhook_id,
            'webhook_event':     json.loads(raw_body),
        }

        response = requests.post(
            verify_url,
            json=verify_payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('verification_status') == 'SUCCESS'

    except Exception:
        return False


def _get_paypal_access_token() -> str:
    """Get PayPal OAuth2 access token"""
    is_sandbox   = getattr(settings, 'PAYPAL_SANDBOX', True)
    client_id    = getattr(settings, 'PAYPAL_CLIENT_ID', '')
    client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', '')

    token_url = (
        'https://api-m.sandbox.paypal.com/v1/oauth2/token'
        if is_sandbox
        else 'https://api-m.paypal.com/v1/oauth2/token'
    )

    try:
        response = requests.post(
            token_url,
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret),
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get('access_token', '')
    except Exception:
        return ''

# api/payment_gateways/integration_system/webhooks_integration.py
# Webhook integration — routes incoming gateway webhooks to handlers

import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .integ_constants import IntegEvent
from .integ_registry import registry

logger = logging.getLogger(__name__)


class WebhookIntegration:
    """
    Central webhook router for all gateway webhooks.

    Receives raw webhook → verifies signature → fires integration events.
    Works alongside your existing api.webhooks app.

    Gateway webhook URLs registered at:
        /api/payment/webhooks/{gateway}/
    """

    GATEWAY_EVENT_MAP = {
        'bkash':     {'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'nagad':     {'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'sslcommerz':{'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'amarpay':   {'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'upay':      {'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'shurjopay': {'success': IntegEvent.DEPOSIT_COMPLETED, 'failed': IntegEvent.DEPOSIT_FAILED},
        'stripe':    {'payment_intent.succeeded': IntegEvent.DEPOSIT_COMPLETED,
                      'payment_intent.payment_failed': IntegEvent.DEPOSIT_FAILED,
                      'charge.refunded': IntegEvent.DEPOSIT_REFUNDED},
        'paypal':    {'PAYMENT.CAPTURE.COMPLETED': IntegEvent.DEPOSIT_COMPLETED,
                      'PAYMENT.CAPTURE.DENIED':    IntegEvent.DEPOSIT_FAILED},
    }

    def process(self, gateway: str, request) -> HttpResponse:
        """
        Process incoming webhook from a gateway.

        Steps:
            1. Verify HMAC signature
            2. Parse payload
            3. Find matching DepositRequest
            4. Fire appropriate integration event
            5. Log everything
        """
        from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService

        body    = request.body
        headers = dict(request.headers)
        ip      = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                  or request.META.get('REMOTE_ADDR', '')

        # 1. Verify signature
        verifier = WebhookVerifierService()
        is_valid = verifier.verify(gateway, body, headers)

        if not is_valid:
            logger.warning(f'WebhookIntegration: invalid signature from {gateway} ip={ip}')
            registry.emit(IntegEvent.WEBHOOK_FAILED,
                          gateway=gateway, reason='invalid_signature', ip=ip)
            return HttpResponse('Invalid signature', status=400)

        # 2. Parse payload
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = dict(request.POST)

        # 3. Fire webhook received event
        registry.emit(IntegEvent.WEBHOOK_RECEIVED,
                       gateway=gateway, payload=payload, is_valid=True)

        # 4. Find and process via DepositService
        try:
            result = self._process_payload(gateway, payload)
            status = 200 if result.get('success', True) else 400
            return HttpResponse('OK' if status == 200 else 'Error', status=status)
        except Exception as e:
            logger.error(f'WebhookIntegration.process {gateway}: {e}')
            return HttpResponse('Processing error', status=500)

    def _process_payload(self, gateway: str, payload: dict) -> dict:
        """Extract reference and route to DepositService."""
        from api.payment_gateways.services.DepositService import DepositService

        # Extract reference ID (differs per gateway)
        ref_extractors = {
            'bkash':      lambda p: p.get('paymentID', ''),
            'nagad':      lambda p: p.get('orderId', ''),
            'sslcommerz': lambda p: p.get('tran_id', ''),
            'amarpay':    lambda p: p.get('mer_txnid', ''),
            'upay':       lambda p: p.get('transaction_id', ''),
            'shurjopay':  lambda p: p.get('sp_order_id', ''),
            'stripe':     lambda p: p.get('data', {}).get('object', {}).get('metadata', {}).get('reference_id', ''),
            'paypal':     lambda p: p.get('resource', {}).get('supplementary_data', {}).get('related_ids', {}).get('order_id', ''),
        }

        ref_id  = ref_extractors.get(gateway, lambda p: p.get('reference_id', ''))(payload)
        gw_ref  = payload.get('trxID', payload.get('id', ref_id))

        if ref_id:
            svc    = DepositService()
            result = svc.verify_and_complete(ref_id, gw_ref, payload)
            return result

        return {'success': False, 'reason': 'reference_id not found in payload'}


class WebhookRetryManager:
    """
    Manages webhook retry logic for failed webhook deliveries.
    Called by webhook_retry_tasks.py
    """

    MAX_RETRIES   = 5
    RETRY_DELAYS  = [60, 300, 900, 3600, 86400]  # 1m, 5m, 15m, 1h, 24h

    def schedule_retry(self, webhook_log_id: int, retry_count: int):
        """Schedule a retry for a failed webhook."""
        if retry_count >= self.MAX_RETRIES:
            logger.warning(f'Webhook {webhook_log_id}: max retries reached, adding to DLQ')
            self._add_to_dlq(webhook_log_id)
            return

        delay = self.RETRY_DELAYS[min(retry_count, len(self.RETRY_DELAYS) - 1)]

        try:
            from api.payment_gateways.tasks.webhook_retry_tasks import retry_failed_webhook
            retry_failed_webhook.apply_async(
                args=[webhook_log_id],
                countdown=delay,
            )
            logger.info(f'Webhook {webhook_log_id}: retry #{retry_count+1} scheduled in {delay}s')
        except Exception as e:
            logger.error(f'Could not schedule webhook retry: {e}')

    def _add_to_dlq(self, webhook_log_id: int):
        from django.core.cache import cache
        dlq = cache.get('webhook_dlq', [])
        dlq.append(webhook_log_id)
        cache.set('webhook_dlq', dlq[-500:], 86400 * 7)

    def get_dlq(self) -> list:
        from django.core.cache import cache
        return cache.get('webhook_dlq', [])

# api/admin_panel/auto_payout.py
"""
Automated Payout Processing Engine.
Processes approved withdrawals via bKash/Nagad/Rocket APIs.
admin_panel orchestrates; api.payment_gateways does the actual API calls.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AutoPayoutEngine:
    """Automated payout processor — calls payment gateway APIs."""

    BATCH_SIZE = 50  # Process 50 at a time

    @classmethod
    def run_auto_payout_batch(cls) -> Dict:
        """Process a batch of approved QUEUED payouts automatically."""
        results = {'processed': 0, 'success': 0, 'failed': 0, 'errors': []}
        try:
            from api.payout_queue.models import PayoutItem, PayoutBatch
            # Get approved items
            items = PayoutItem.objects.filter(
                status='SUCCESS',  # Approved and ready
                gateway_reference=''  # Not yet sent to gateway
            ).select_related('user', 'batch')[:cls.BATCH_SIZE]

            for item in items:
                try:
                    result = cls._process_item(item)
                    results['processed'] += 1
                    if result.get('success'):
                        results['success'] += 1
                        item.gateway_reference = result.get('reference', '')
                        item.save(update_fields=['gateway_reference'])
                    else:
                        results['failed'] += 1
                        item.error_message = result.get('error', '')[:500]
                        item.status = 'FAILED'
                        item.retry_count += 1
                        item.save(update_fields=['error_message', 'status', 'retry_count'])
                except Exception as e:
                    results['errors'].append(str(e))
                    results['failed'] += 1
        except Exception as e:
            logger.error(f"[AutoPayout] Batch run failed: {e}")
            results['errors'].append(str(e))
        return results

    @classmethod
    def _process_item(cls, item) -> Dict:
        """Process a single payout item via payment gateway."""
        try:
            from api.payment_gateways.models import PaymentGateway
            gw = PaymentGateway.objects.get(name=item.gateway, is_active=True)
            # Call gateway-specific processor
            return cls._call_gateway(
                gateway_type=item.gateway,
                account_number=item.account_number,
                amount=float(item.net_amount),
                reference=item.internal_reference,
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _call_gateway(cls, gateway_type: str, account_number: str,
                      amount: float, reference: str) -> Dict:
        """Call the appropriate payment gateway API."""
        processors = {
            'BKASH':  cls._process_bkash,
            'NAGAD':  cls._process_nagad,
            'ROCKET': cls._process_rocket,
            'BANK':   cls._process_bank,
        }
        processor = processors.get(gateway_type, cls._process_manual)
        return processor(account_number, amount, reference)

    @classmethod
    def _process_bkash(cls, account: str, amount: float, reference: str) -> Dict:
        """Process bKash payout via API."""
        from django.conf import settings
        app_key    = getattr(settings, 'BKASH_APP_KEY', '')
        app_secret = getattr(settings, 'BKASH_APP_SECRET', '')
        if not app_key:
            return {'success': False, 'error': 'bKash not configured'}
        try:
            import requests
            # B2C disbursement API
            resp = requests.post(
                'https://tokenized.pay.bka.sh/v1.2.0-beta/tokenized/checkout/transfer',
                headers={'X-APP-Key': app_key, 'Authorization': f'Bearer {cls._get_bkash_token(app_key, app_secret)}',
                         'Content-Type': 'application/json'},
                json={'mode': '0011', 'payerReference': ' ', 'callbackURL': '',
                      'amount': str(amount), 'currency': 'BDT',
                      'intent': 'sale', 'merchantInvoiceNumber': reference},
                timeout=15
            )
            data = resp.json()
            if data.get('statusCode') == '0000':
                return {'success': True, 'reference': data.get('trxID', ''), 'provider': 'bkash'}
            return {'success': False, 'error': data.get('statusMessage', 'bKash API error')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _get_bkash_token(cls, app_key: str, app_secret: str) -> str:
        cache_key = 'admin_panel:bkash_token'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            import requests
            resp = requests.post(
                'https://tokenized.pay.bka.sh/v1.2.0-beta/tokenized/checkout/token/grant',
                headers={'username': app_key, 'password': app_secret, 'Content-Type': 'application/json'},
                json={'app_key': app_key, 'app_secret': app_secret},
                timeout=10
            )
            token = resp.json().get('id_token', '')
            if token:
                cache.set(cache_key, token, 3500)
            return token
        except Exception:
            return ''

    @classmethod
    def _process_nagad(cls, account: str, amount: float, reference: str) -> Dict:
        """Process Nagad payout via API."""
        from django.conf import settings
        merchant_id = getattr(settings, 'NAGAD_MERCHANT_ID', '')
        if not merchant_id:
            return {'success': False, 'error': 'Nagad not configured'}
        # Nagad B2C API implementation
        logger.info(f"[AutoPayout] Nagad: {account} ৳{amount}")
        return {'success': False, 'error': 'Nagad B2C API: contact support to enable'}

    @classmethod
    def _process_rocket(cls, account: str, amount: float, reference: str) -> Dict:
        """Process Rocket (DBBL) payout."""
        return {'success': False, 'error': 'Rocket B2C: manual processing required'}

    @classmethod
    def _process_bank(cls, account: str, amount: float, reference: str) -> Dict:
        """Process bank transfer — queues for manual processing."""
        return {'success': False, 'error': 'Bank transfer: manual processing required', 'manual': True}

    @classmethod
    def _process_manual(cls, account: str, amount: float, reference: str) -> Dict:
        return {'success': False, 'error': 'Manual gateway: requires human review'}

    @classmethod
    def get_auto_payout_stats(cls) -> Dict:
        from api.payout_queue.models import PayoutItem
        from django.db.models import Count, Sum
        today = timezone.now().date()
        return {
            'queued':    PayoutItem.objects.filter(status='QUEUED').aggregate(c=Count('id'), a=Sum('gross_amount')),
            'processing': PayoutItem.objects.filter(status='PROCESSING').count(),
            'success_today': PayoutItem.objects.filter(status='SUCCESS',
                             processed_at__date=today).aggregate(c=Count('id'), a=Sum('net_amount')),
            'failed_today':  PayoutItem.objects.filter(status='FAILED',
                             processed_at__date=today).count(),
        }


auto_payout = AutoPayoutEngine()
# api/payment_gateways/services/WithdrawalGatewayService.py
import logging
from decimal import Decimal
from django.utils import timezone
logger = logging.getLogger(__name__)


class WithdrawalGatewayService:
    """
    Orchestrates gateway-level payout execution.
    Called after admin approves a PayoutRequest.

    Flow:
        1. Create WithdrawalGatewayRequest record
        2. Call gateway processor
        3. Record response
        4. On failure: create WithdrawalFailure + retry logic
    """

    def execute(self, payout_request) -> dict:
        """Execute approved payout via gateway."""
        from .PaymentFactory import PaymentFactory
        from api.payment_gateways.models.withdrawal import (
            WithdrawalGatewayRequest, WithdrawalFailure, WithdrawalReceipt
        )
        from api.payment_gateways.models.core import PayoutRequest

        gateway = payout_request.payout_method

        gw_req = WithdrawalGatewayRequest.objects.create(
            payout_request_id=payout_request.id,
            gateway=gateway,
            request_payload={
                'amount':  str(payout_request.net_amount),
                'account': payout_request.account_number,
                'method':  gateway,
            },
            status='queued',
        )

        try:
            processor = PaymentFactory.get_processor(gateway)

            class _PaymentMethod:
                account_number = payout_request.account_number
                account_name   = payout_request.account_name
                gateway        = payout_request.payout_method

            result = processor.process_withdrawal(
                user=payout_request.user,
                amount=payout_request.net_amount,
                payment_method=_PaymentMethod(),
                metadata={'payout_request_id': payout_request.id}
            )

            gw_ref = ''
            if hasattr(result.get('payout', None), 'reference_id'):
                gw_ref = result['payout'].reference_id

            gw_req.status           = 'sent'
            gw_req.gateway_ref      = gw_ref
            gw_req.response_payload = result
            gw_req.sent_at          = timezone.now()
            gw_req.save()

            payout_request.status           = 'processing'
            payout_request.gateway_reference= gw_ref
            payout_request.save(update_fields=['status', 'gateway_reference'])

            # Generate receipt
            self._generate_receipt(payout_request, gw_ref)

            logger.info(f'Withdrawal executed: id={payout_request.id} gateway={gateway}')
            return {'success': True, 'gateway_ref': gw_ref, 'gateway': gateway}

        except Exception as e:
            gw_req.status        = 'failed'
            gw_req.error_message = str(e)
            gw_req.save()

            retry_count = WithdrawalFailure.objects.filter(
                payout_request_id=payout_request.id
            ).count()

            failure = WithdrawalFailure.objects.create(
                payout_request_id=payout_request.id,
                gateway=gateway,
                failure_type='gateway_error',
                error_message=str(e),
                retry_count=retry_count + 1,
                is_final=(retry_count >= 3),
            )

            if failure.is_final:
                payout_request.status = 'failed'
                payout_request.save(update_fields=['status'])

            logger.error(f'Withdrawal failed: id={payout_request.id} error={e}')
            raise

    def execute_batch(self, payout_ids: list) -> dict:
        """Process multiple payouts in batch."""
        from api.payment_gateways.models.core import PayoutRequest
        results = {'success': 0, 'failed': 0, 'errors': []}
        for pid in payout_ids:
            try:
                p = PayoutRequest.objects.get(id=pid, status='approved')
                self.execute(p)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({'id': pid, 'error': str(e)})
        return results

    def _generate_receipt(self, payout_request, gateway_ref: str):
        from api.payment_gateways.models.withdrawal import WithdrawalReceipt
        import time
        try:
            WithdrawalReceipt.objects.get_or_create(
                payout_request_id=payout_request.id,
                defaults={
                    'receipt_number': f'RCP-{int(time.time()*1000)}',
                    'user_name':      payout_request.user.get_full_name() or payout_request.user.username,
                    'user_email':     payout_request.user.email,
                    'gateway_display':payout_request.payout_method.upper(),
                    'account_display':payout_request.account_number[-4:].rjust(len(payout_request.account_number), '*'),
                    'amount':         payout_request.amount,
                    'fee':            payout_request.fee,
                    'net_amount':     payout_request.net_amount,
                    'currency':       payout_request.currency,
                    'reference':      payout_request.reference_id,
                    'gateway_ref':    gateway_ref,
                }
            )
        except Exception as e:
            logger.warning(f'Receipt generation failed: {e}')

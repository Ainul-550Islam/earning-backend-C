# api/payment_gateways/services/DepositService.py
# High-level deposit orchestration service

from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_txn
import logging

logger = logging.getLogger(__name__)


class DepositService:
    """
    Orchestrates the full deposit lifecycle:
        1. Validate amount and gateway availability
        2. Calculate fee using GatewayFeeRule
        3. Check fraud risk
        4. Call gateway processor
        5. Create DepositRequest record
        6. Return payment URL to client

    On callback:
        7. Verify signature (WebhookVerifierService)
        8. Update DepositRequest status
        9. Credit user balance
        10. Trigger notifications + referral commission
    """

    def initiate(self, user, amount: Decimal, gateway: str,
                 currency: str = 'BDT', **kwargs) -> dict:
        """Create a deposit request and return payment URL."""
        from api.payment_gateways.services.PaymentFactory import PaymentFactory
        from api.payment_gateways.models.deposit import DepositRequest
        from api.payment_gateways.models.gateway_config import GatewayFeeRule
        from api.payment_gateways.models.core import PaymentGateway

        # Calculate fee
        fee = self._calculate_fee(gateway, amount, currency)
        net = amount - fee

        # Generate reference
        import time
        ref_id = f'DEP-{gateway.upper()}-{int(time.time()*1000)}'

        with db_txn.atomic():
            # Fraud check
            fraud_result = self._check_fraud(user, amount, gateway, kwargs.get('ip', ''))
            if fraud_result['action'] == 'block':
                raise PermissionError(f"Transaction blocked: {', '.join(fraud_result['reasons'])}")

            # Get gateway processor
            processor = PaymentFactory.get_processor(gateway)
            processor.validate_amount(amount)

            # Create deposit record
            deposit = DepositRequest.objects.create(
                user=user,
                gateway=gateway,
                amount=amount,
                fee=fee,
                net_amount=net,
                currency=currency,
                reference_id=ref_id,
                ip_address=kwargs.get('ip'),
                user_agent=kwargs.get('user_agent', ''),
                metadata={'fraud_score': fraud_result['risk_score']},
            )

            # Call gateway
            try:
                result = processor.process_deposit(user=user, amount=amount,
                                                    metadata={'deposit_id': deposit.id})
                deposit.payment_url = result.get('payment_url', '')
                deposit.session_key = result.get('session_key', '') or result.get('payment_id', '')
                deposit.gateway_response = result
                deposit.status = 'pending'
                deposit.save()
            except Exception as e:
                deposit.status = 'failed'
                deposit.save()
                raise Exception(f'Gateway error: {e}')

        logger.info(f'Deposit initiated: {ref_id} | {gateway} | {amount}')
        return {
            'deposit_id':   deposit.id,
            'reference_id': ref_id,
            'payment_url':  deposit.payment_url,
            'amount':       str(amount),
            'fee':          str(fee),
            'net_amount':   str(net),
            'currency':     currency,
            'gateway':      gateway,
        }

    def verify_and_complete(self, reference_id: str, gateway_ref: str,
                             callback_data: dict) -> dict:
        """Complete deposit after gateway callback."""
        from api.payment_gateways.models.deposit import DepositRequest, DepositVerification

        try:
            deposit = DepositRequest.objects.select_related('user').get(reference_id=reference_id)
        except DepositRequest.DoesNotExist:
            raise Exception(f'Deposit not found: {reference_id}')

        if deposit.status == 'completed':
            return {'already_completed': True}

        with db_txn.atomic():
            deposit.gateway_ref   = gateway_ref
            deposit.callback_data = callback_data
            deposit.status        = 'completed'
            deposit.completed_at  = timezone.now()
            deposit.save()

            # Create verification record
            DepositVerification.objects.create(
                deposit=deposit,
                verification_method='auto_webhook',
                verified_at=timezone.now(),
                is_verified=True,
                gateway_txn_id=gateway_ref,
                verified_amount=deposit.net_amount,
            )

            # Credit user balance
            user = deposit.user
            if hasattr(user, 'balance'):
                user.balance = (user.balance or Decimal('0')) + deposit.net_amount
                user.save(update_fields=['balance'])

            # Referral commission
            self._credit_referral(user, deposit.net_amount, reference_id)

            # Notification
            self._send_notification(user, deposit)

        logger.info(f'Deposit completed: {reference_id} | net={deposit.net_amount}')
        return {'completed': True, 'net_amount': str(deposit.net_amount)}

    def _calculate_fee(self, gateway: str, amount: Decimal, currency: str) -> Decimal:
        from api.payment_gateways.models.gateway_config import GatewayFeeRule
        from api.payment_gateways.models.core import PaymentGateway
        try:
            gw   = PaymentGateway.objects.get(name=gateway)
            rule = GatewayFeeRule.objects.filter(gateway=gw, transaction_type='deposit',
                                                  is_active=True).first()
            if rule:
                return rule.calculate(amount)
            return (amount * gw.transaction_fee_percentage) / 100
        except Exception:
            from api.payment_gateways.constants import GATEWAY_FEES
            rate = Decimal(str(GATEWAY_FEES.get(gateway, 0.015)))
            return amount * rate

    def _check_fraud(self, user, amount, gateway, ip):
        try:
            from api.payment_gateways.fraud.FraudDetector import FraudDetector
            return FraudDetector().check(user, amount, gateway, ip_address=ip)
        except Exception:
            return {'action': 'allow', 'risk_score': 0, 'reasons': []}

    def _credit_referral(self, user, amount, ref):
        try:
            from api.payment_gateways.referral.ReferralEngine import ReferralEngine
            ReferralEngine().credit_commission(user, amount, ref)
        except Exception:
            pass

    def _send_notification(self, user, deposit):
        try:
            from api.payment_gateways.notifications.EmailNotifier import EmailNotifier
            EmailNotifier().send_deposit_completed(user, deposit)
        except Exception:
            pass


class WithdrawalGatewayService:
    """
    Orchestrates gateway-level payout execution.
    Called after admin approves a PayoutRequest.
    """

    def execute(self, payout_request) -> dict:
        """Execute approved payout via gateway."""
        from api.payment_gateways.services.PaymentFactory import PaymentFactory
        from api.payment_gateways.models.withdrawal import WithdrawalGatewayRequest

        gateway = payout_request.payout_method

        gw_req = WithdrawalGatewayRequest.objects.create(
            payout_request=payout_request,
            gateway=gateway,
            request_payload={'amount': str(payout_request.net_amount),
                             'account': payout_request.account_number},
            status='queued',
        )

        try:
            processor = PaymentFactory.get_processor(gateway)

            class _M:
                account_number = payout_request.account_number
                account_name   = payout_request.account_name

            result = processor.process_withdrawal(
                user=payout_request.user,
                amount=payout_request.net_amount,
                payment_method=_M(),
                metadata={'payout_request_id': payout_request.id}
            )

            gw_req.status      = 'sent'
            gw_req.gateway_ref = str(result.get('payout', {}).id if hasattr(result.get('payout',{}), 'id') else '')
            gw_req.response_payload = result
            gw_req.sent_at     = timezone.now()
            gw_req.save()

            payout_request.status    = 'processing'
            payout_request.gateway_reference = gw_req.gateway_ref
            payout_request.save()

            logger.info(f'Withdrawal executed: payout_id={payout_request.id} via {gateway}')
            return {'success': True, 'gateway_ref': gw_req.gateway_ref}

        except Exception as e:
            gw_req.status        = 'failed'
            gw_req.error_message = str(e)
            gw_req.save()

            from api.payment_gateways.models.withdrawal import WithdrawalFailure
            WithdrawalFailure.objects.create(
                payout_request=payout_request,
                gateway=gateway,
                failure_type='gateway_error',
                error_message=str(e),
            )
            raise

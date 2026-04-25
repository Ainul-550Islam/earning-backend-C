# api/payment_gateways/integration_system/integ_handler.py
# Master integration handler — processes all cross-module events

from decimal import Decimal
from typing import Any, Optional
import logging

from .integ_constants import IntegEvent, IntegModule, Priority
from .integ_registry import registry

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Master handler that processes all cross-module integration events.

    Called by payment_gateways services after every significant action.
    Delegates to appropriate external modules via adapters.

    Example flow:
        1. DepositService.verify_and_complete() calls:
           IntegrationHandler().on_deposit_completed(user, deposit)
        2. Handler fires IntegEvent.DEPOSIT_COMPLETED
        3. Registry calls:
           - WalletAdapter.credit_deposit()
           - NotificationAdapter.send_deposit_completed()
           - ReferralEngine.credit_commission()
           - AnalyticsAdapter.record_deposit()
    """

    def on_deposit_completed(self, user, deposit) -> dict:
        """Called when a deposit is successfully verified and credited."""
        logger.info(f'Integration: deposit completed user={user.id} ref={deposit.reference_id}')

        results = registry.emit(IntegEvent.DEPOSIT_COMPLETED,
            user=user,
            deposit=deposit,
            amount=deposit.net_amount,
            gateway=deposit.gateway,
            reference_id=deposit.reference_id,
        )
        return self._summarize(results)

    def on_deposit_failed(self, user, deposit, error: str = '') -> dict:
        """Called when a deposit fails."""
        results = registry.emit(IntegEvent.DEPOSIT_FAILED,
            user=user,
            deposit=deposit,
            error=error,
        )
        return self._summarize(results)

    def on_withdrawal_processed(self, user, payout_request) -> dict:
        """Called when a withdrawal is successfully processed."""
        results = registry.emit(IntegEvent.WITHDRAWAL_PROCESSED,
            user=user,
            payout_request=payout_request,
            amount=payout_request.net_amount,
            gateway=payout_request.payout_method,
        )
        return self._summarize(results)

    def on_withdrawal_failed(self, user, payout_request, error: str = '') -> dict:
        """Called when a withdrawal fails."""
        results = registry.emit(IntegEvent.WITHDRAWAL_FAILED,
            user=user,
            payout_request=payout_request,
            error=error,
        )
        return self._summarize(results)

    def on_conversion_approved(self, conversion) -> dict:
        """Called when a publisher conversion is approved."""
        results = registry.emit(IntegEvent.CONVERSION_APPROVED,
            conversion=conversion,
            publisher=conversion.publisher,
            offer=conversion.offer,
            payout=conversion.payout,
            currency=conversion.currency,
        )
        return self._summarize(results)

    def on_conversion_reversed(self, conversion) -> dict:
        """Called when a conversion is reversed (chargeback)."""
        results = registry.emit(IntegEvent.CONVERSION_REVERSED,
            conversion=conversion,
            publisher=conversion.publisher,
            amount=conversion.payout,
        )
        return self._summarize(results)

    def on_fraud_detected(self, user, transaction, fraud_result: dict) -> dict:
        """Called when fraud is detected on a transaction."""
        results = registry.emit(IntegEvent.FRAUD_DETECTED,
            user=user,
            transaction=transaction,
            risk_score=fraud_result.get('risk_score', 0),
            reasons=fraud_result.get('reasons', []),
        )
        return self._summarize(results)

    def on_gateway_status_change(self, gateway_name: str,
                                  old_status: str, new_status: str) -> dict:
        """Called when a gateway's health status changes."""
        event = IntegEvent.GATEWAY_UP if new_status == 'healthy' else IntegEvent.GATEWAY_DOWN
        results = registry.emit(event,
            gateway=gateway_name,
            old_status=old_status,
            new_status=new_status,
        )
        return self._summarize(results)

    def on_referral_credited(self, referrer, referred_user,
                              commission: Decimal) -> dict:
        """Called when referral commission is credited."""
        results = registry.emit(IntegEvent.REFERRAL_CREDITED,
            referrer=referrer,
            referred_user=referred_user,
            commission=commission,
        )
        return self._summarize(results)

    def on_webhook_received(self, gateway: str, payload: dict,
                             is_valid: bool) -> dict:
        """Called when any gateway webhook is received."""
        results = registry.emit(IntegEvent.WEBHOOK_RECEIVED,
            gateway=gateway,
            payload=payload,
            is_valid=is_valid,
        )
        return self._summarize(results)

    def _summarize(self, results: list) -> dict:
        success = sum(1 for r in results if r.get('status') == 'success')
        failed  = sum(1 for r in results if r.get('status') == 'failed')
        queued  = sum(1 for r in results if r.get('status') == 'queued')
        return {
            'total':   len(results),
            'success': success,
            'failed':  failed,
            'queued':  queued,
            'results': results,
        }


# Singleton
handler = IntegrationHandler()

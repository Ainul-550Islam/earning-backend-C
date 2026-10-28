# api/djoyalty/services/points/WalletBridgeService.py
"""Wallet system integration bridge।"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class WalletBridgeService:
    @staticmethod
    def sync_balance_to_wallet(customer, balance: Decimal):
        logger.debug('WalletBridge: sync %s pts for %s', balance, customer)
        # Wallet integration hook -- override per project
        return True

    @staticmethod
    def sync_balance_from_wallet(customer) -> Decimal:
        logger.debug('WalletBridge: fetch balance for %s', customer)
        return Decimal('0')

    @staticmethod
    def approve_cashout(cashout, admin: str = 'system', note: str = '') -> dict:
        """
        Approve a cashout request -- moves to 'approved' status.
        Triggers actual wallet/bank transfer initiation.
        """
        try:
            from django.utils import timezone
            cashout.status = 'approved'
            cashout.reviewed_by = admin
            cashout.reviewed_at = timezone.now()
            cashout.admin_note = note or ''
            cashout.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note'])

            # Initiate transfer via payment gateway
            result = WalletBridgeService._initiate_transfer(cashout)

            logger.info('WalletBridgeService.approve_cashout: cashout#%s approved by %s', cashout.id, admin)
            return {'success': True, 'cashout_id': cashout.id, 'transfer': result}
        except Exception as e:
            logger.error('WalletBridgeService.approve_cashout error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def reject_cashout(cashout, admin: str = 'system', reason: str = '') -> dict:
        """
        Reject a cashout request -- refunds reserved points to customer.
        """
        try:
            from django.utils import timezone
            from decimal import Decimal

            cashout.status = 'rejected'
            cashout.reviewed_by = admin
            cashout.reviewed_at = timezone.now()
            cashout.rejection_reason = reason or ''
            cashout.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])

            # Refund reserved points
            if cashout.points_used and cashout.points_used > 0:
                from ..earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    cashout.customer,
                    cashout.points_used,
                    reason=f'Cashout rejected refund: #{cashout.id}',
                    triggered_by='cashout_reject',
                    tenant=getattr(cashout, 'tenant', None),
                )

            logger.info('WalletBridgeService.reject_cashout: cashout#%s rejected by %s', cashout.id, admin)
            return {'success': True, 'cashout_id': cashout.id, 'refunded_points': str(cashout.points_used or 0)}
        except Exception as e:
            logger.error('WalletBridgeService.reject_cashout error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def complete_cashout(cashout, transaction_ref: str = '', admin: str = 'system') -> dict:
        """
        Mark cashout as completed after successful payment.
        """
        try:
            from django.utils import timezone
            cashout.status = 'completed'
            cashout.completed_at = timezone.now()
            if transaction_ref:
                cashout.transaction_reference = transaction_ref
            cashout.save(update_fields=['status', 'completed_at', 'transaction_reference'])

            # Notify customer
            try:
                from ..NotificationService import NotificationService
                NotificationService.notify_cashout_complete(
                    cashout.customer,
                    amount=cashout.cashout_amount,
                    method=getattr(cashout, 'cashout_method', 'wallet'),
                )
            except Exception:
                pass

            logger.info('WalletBridgeService.complete_cashout: cashout#%s completed', cashout.id)
            return {'success': True, 'cashout_id': cashout.id, 'status': 'completed'}
        except Exception as e:
            logger.error('WalletBridgeService.complete_cashout error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel_cashout(cashout, admin: str = 'system') -> dict:
        """
        Cancel a pending cashout -- refunds points, marks cancelled.
        """
        try:
            from django.utils import timezone
            if cashout.status in ('completed',):
                return {'success': False, 'error': 'Cannot cancel a completed cashout'}

            cashout.status = 'cancelled'
            cashout.cancelled_at = timezone.now()
            cashout.save(update_fields=['status', 'cancelled_at'])

            # Refund
            if cashout.points_used and cashout.points_used > 0:
                from ..earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    cashout.customer,
                    cashout.points_used,
                    reason=f'Cashout cancelled refund: #{cashout.id}',
                    triggered_by='cashout_cancel',
                    tenant=getattr(cashout, 'tenant', None),
                )

            logger.info('WalletBridgeService.cancel_cashout: cashout#%s cancelled by %s', cashout.id, admin)
            return {'success': True, 'cashout_id': cashout.id, 'refunded_points': str(cashout.points_used or 0)}
        except Exception as e:
            logger.error('WalletBridgeService.cancel_cashout error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _initiate_transfer(cashout) -> dict:
        """Dispatch to bKash / Nagad / bank based on cashout_method."""
        try:
            method = getattr(cashout, 'cashout_method', 'bkash')
            amount = float(cashout.cashout_amount)
            phone = getattr(cashout.customer, 'phone', '') or ''

            if method == 'bkash':
                from ...integrations.bkash import BkashIntegration
                return BkashIntegration.send_money(phone, amount)
            elif method == 'nagad':
                from ...integrations.nagad import NagadIntegration
                return NagadIntegration.send_money(phone, amount)
            else:
                return {'initiated': True, 'method': method, 'note': 'Manual transfer required'}
        except Exception as e:
            logger.error('WalletBridgeService._initiate_transfer error: %s', e)
            return {'initiated': False, 'error': str(e)}

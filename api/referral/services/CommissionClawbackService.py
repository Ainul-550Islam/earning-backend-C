# api/referral/services/CommissionClawbackService.py
# Reverse commission on fraud or refund
# ============================================================

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class CommissionClawbackService:
    """
    Commission clawback — fraud বা refund এ commission reverse।
    Admin approve → Celery task process।
    """

    @staticmethod
    @transaction.atomic
    def initiate_clawback(
        commission_log_id: int,
        reason: str,
        reason_detail: str = '',
        partial_amount: Decimal = None,
    ) -> dict:
        """
        Clawback initiate করো (pending approval)।
        """
        from api.referral.models import CommissionLog, CommissionClawback

        try:
            log = CommissionLog.objects.get(id=commission_log_id)
        except CommissionLog.DoesNotExist:
            return {'success': False, 'error': 'Commission log not found'}

        if log.status == 'clawed_back':
            return {'success': False, 'error': 'Already clawed back'}

        clawback_amount = partial_amount or log.amount

        if clawback_amount > log.amount:
            return {
                'success': False,
                'error': 'Clawback amount exceeds commission amount'
            }

        clawback = CommissionClawback.objects.create(
            commission=log,
            reason=reason,
            reason_detail=reason_detail,
            clawback_amount=clawback_amount,
            status='pending',
        )

        logger.info(
            f"Clawback initiated: commission={log.id}, "
            f"amount={clawback_amount}, reason={reason}"
        )

        return {
            'success': True,
            'clawback_id': clawback.id,
            'clawback_amount': float(clawback_amount),
            'status': 'pending',
        }

    @staticmethod
    @transaction.atomic
    def approve_clawback(clawback_id: int, admin_user) -> dict:
        """Admin clawback approve করুক।"""
        from api.referral.models import CommissionClawback

        try:
            clawback = CommissionClawback.objects.select_related(
                'commission', 'commission__user'
            ).get(id=clawback_id, status='pending')
        except CommissionClawback.DoesNotExist:
            return {'success': False, 'error': 'Clawback not found or not pending'}

        clawback.approve(admin_user)

        logger.info(
            f"Clawback approved: {clawback.id} by {admin_user.username}"
        )

        return {
            'success': True,
            'clawback_id': clawback.id,
            'status': 'approved',
        }

    @staticmethod
    @transaction.atomic
    def reject_clawback(clawback_id: int, admin_user) -> dict:
        """Admin clawback reject করুক।"""
        from api.referral.models import CommissionClawback

        try:
            clawback = CommissionClawback.objects.get(
                id=clawback_id, status='pending'
            )
        except CommissionClawback.DoesNotExist:
            return {'success': False, 'error': 'Clawback not found or not pending'}

        clawback.reject(admin_user)

        return {
            'success': True,
            'clawback_id': clawback.id,
            'status': 'rejected',
        }

    @staticmethod
    @transaction.atomic
    def process_approved_clawback(clawback_id: int) -> dict:
        """
        Approved clawback process করো।
        Wallet থেকে commission deduct করো।
        Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import CommissionClawback

        try:
            clawback = CommissionClawback.objects.select_related(
                'commission', 'commission__user'
            ).get(id=clawback_id, status='approved')
        except CommissionClawback.DoesNotExist:
            return {
                'success': False,
                'error': 'Clawback not found or not approved'
            }

        user = clawback.commission.user

        try:
            from api.wallet.services import WalletService
            from api.wallet.models import Wallet

            wallet, _ = Wallet.objects.get_or_create(user=user)

            # Wallet থেকে deduct করো
            wallet_txn = WalletService.deduct_balance(
                wallet=wallet,
                amount=clawback.clawback_amount,
                description=(
                    f"Commission clawback: {clawback.get_reason_display()}"
                ),
                source_type='referral_clawback',
                source_id=str(clawback.id),
            )

            clawback.mark_completed(
                wallet_txn_id=str(
                    getattr(wallet_txn, 'walletTransaction_id', '')
                )
            )

            logger.info(
                f"Clawback processed: {clawback.id} "
                f"deducted ৳{clawback.clawback_amount} "
                f"from {user.username}"
            )

            return {
                'success': True,
                'clawback_id': clawback.id,
                'amount_deducted': float(clawback.clawback_amount),
                'user': user.username,
            }

        except Exception as e:
            clawback.status = 'failed'
            clawback.save(update_fields=['status'])
            logger.error(f"Clawback processing error: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_all_approved(dry_run: bool = False) -> dict:
        """
        সব approved clawbacks process করো।
        Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import CommissionClawback

        approved = CommissionClawback.objects.filter(status='approved')
        processed = 0
        errors = 0
        total_clawed = Decimal('0')

        for clawback in approved:
            if dry_run:
                processed += 1
                total_clawed += clawback.clawback_amount
                continue

            result = CommissionClawbackService.process_approved_clawback(
                clawback.id
            )
            if result['success']:
                processed += 1
                total_clawed += clawback.clawback_amount
            else:
                errors += 1

        return {
            'processed': processed,
            'errors': errors,
            'total_clawed': float(total_clawed),
            'dry_run': dry_run,
        }

    @staticmethod
    def bulk_initiate_for_fraud(referral_id: int, reason_detail: str = '') -> dict:
        """
        Fraud confirm হলে referral এর সব commissions এ clawback initiate।
        """
        from api.referral.models import CommissionLog

        logs = CommissionLog.objects.filter(
            referred_user__referral_referral_referred_user__id=referral_id,
            status__in=['released', 'pending', 'held'],
        )

        initiated = 0
        for log in logs:
            result = CommissionClawbackService.initiate_clawback(
                commission_log_id=log.id,
                reason='fraud',
                reason_detail=reason_detail or f"Fraud on referral {referral_id}",
            )
            if result['success']:
                initiated += 1

        return {
            'initiated': initiated,
            'referral_id': referral_id,
        }
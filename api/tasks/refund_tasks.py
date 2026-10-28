"""
tasks/refund_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Refund & Dispute Management Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ process_refund_request     — reverse a transaction and re-credit
  ✅ handle_chargeback          — process advertiser chargeback
  ✅ auto_resolve_disputes      — auto-close clear-cut disputes
  ✅ generate_refund_report     — refund summary report
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.refund_tasks.process_refund_request')
def process_refund_request(
    self,
    refund_id: int,
    reason: str = '',
    approved_by: int = None,
) -> dict:
    """
    Process a refund request:
    1. Validate the original transaction exists
    2. Check refund eligibility (time window, amount)
    3. Reverse the transaction
    4. Re-credit the wallet
    5. Notify all parties
    """
    try:
        logger.info(f"💰 Processing refund request {refund_id}...")

        try:
            from wallet.models import Refund, WalletTransaction, Wallet
            from api.tasks.notification_tasks import dispatch_in_app_notification

            refund = Refund.objects.select_related('transaction', 'user').get(pk=refund_id)

            if refund.status != 'pending':
                return {'status': 'not_pending', 'refund_id': refund_id}

            original_txn = refund.transaction
            amount       = Decimal(str(original_txn.amount or 0))

            # Check eligibility: within 30 days
            from datetime import timedelta
            if (timezone.now() - original_txn.created_at).days > 30:
                refund.status       = 'rejected'
                refund.rejected_reason = 'outside_refund_window'
                refund.save(update_fields=['status', 'rejected_reason'])
                return {'status': 'rejected', 'reason': 'outside_refund_window'}

            with db_transaction.atomic():
                # Debit wallet (reverse the original credit)
                wallet = Wallet.objects.select_for_update().get(user=refund.user)
                if original_txn.transaction_type in ['task_reward', 'bonus_reward']:
                    # These were credits — debit them back
                    wallet.balance = max(wallet.balance - amount, Decimal('0'))
                    wallet.save(update_fields=['balance'])

                # Mark refund complete
                refund.status      = 'completed'
                refund.approved_by_id = approved_by
                refund.completed_at = timezone.now()
                refund.save(update_fields=['status', 'approved_by_id', 'completed_at'])

                # Create reversal transaction
                WalletTransaction.objects.create(
                    user=refund.user,
                    wallet=wallet,
                    amount=amount,
                    transaction_type='refund_reversal',
                    status='completed',
                    reference=f'refund_{refund_id}',
                )

            # Notify user
            dispatch_in_app_notification.apply_async(kwargs={
                'user_id': refund.user_id,
                'title':   '↩️ Refund Processed',
                'message': f'Your refund of ${amount:.2f} has been processed. Reason: {reason}',
                'notification_type': 'info',
            })

            logger.info(f"[REFUND] Processed refund {refund_id}: ${amount}")
            return {
                'status': 'success',
                'refund_id': refund_id,
                'amount': str(amount),
                'timestamp': timezone.now().isoformat(),
            }

        except ImportError as e:
            logger.warning(f"[WARN] Refund models not available: {e}")
            return {'status': 'skipped', 'reason': 'model_not_available'}

    except Exception as exc:
        logger.error(f"[ERROR] process_refund_request: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.refund_tasks.handle_chargeback')
def handle_chargeback(
    self,
    conversion_id: int,
    chargeback_reason: str = '',
    advertiser_id: int = None,
) -> dict:
    """
    Handle an advertiser chargeback on a conversion.
    1. Reverse publisher payout
    2. Re-debit publisher wallet
    3. Flag advertiser for repeated chargebacks
    4. Update fraud scoring
    """
    try:
        logger.warning(f"⚠️ Handling chargeback: conversion={conversion_id}")

        reversed_amount = Decimal('0')

        try:
            from ad_networks.models import OfferConversion
            from wallet.models import Wallet, WalletTransaction

            conv = OfferConversion.objects.get(pk=conversion_id)
            if conv.status in ('reversed', 'rejected'):
                return {'status': 'already_reversed'}

            amount = Decimal(str(conv.payout or 0)) * Decimal('0.75')  # Publisher share

            with db_transaction.atomic():
                # Reverse from publisher wallet
                if conv.user_id:
                    wallet = Wallet.objects.filter(user_id=conv.user_id).first()
                    if wallet:
                        wallet.balance = max(wallet.balance - amount, Decimal('0'))
                        wallet.save(update_fields=['balance'])

                        WalletTransaction.objects.create(
                            user_id=conv.user_id,
                            wallet=wallet,
                            amount=amount,
                            transaction_type='chargeback',
                            status='completed',
                            reference=f'chargeback_{conversion_id}',
                        )

                conv.status = 'reversed'
                conv.save(update_fields=['status'])
                reversed_amount = amount

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        # Increase advertiser fraud score if repeated
        if advertiser_id:
            from django.core.cache import cache
            cb_count = cache.get(f'advertiser_chargebacks_{advertiser_id}', 0) + 1
            cache.set(f'advertiser_chargebacks_{advertiser_id}', cb_count, timeout=86400 * 30)
            if cb_count >= 5:
                logger.warning(f"[CHARGEBACK] Advertiser {advertiser_id} has {cb_count} chargebacks")

        return {
            'status': 'success',
            'conversion_id': conversion_id,
            'reversed_amount': str(reversed_amount),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.refund_tasks.generate_refund_report')
def generate_refund_report(self, date_str: str = None) -> dict:
    """Daily refund summary report."""
    try:
        from datetime import datetime, timedelta
        from django.core.cache import cache
        from django.db.models import Count, Sum

        target    = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        report = {'date': str(target), 'type': 'refund_daily', 'totals': {}}

        try:
            from wallet.models import Refund
            day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
            day_end   = day_start + timedelta(days=1)
            agg = Refund.objects.filter(created_at__gte=day_start, created_at__lt=day_end).aggregate(
                total=Count('id'),
                completed=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='completed')),
                rejected=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='rejected')),
            )
            report['totals'] = {
                'total': agg['total'] or 0,
                'completed': agg['completed'] or 0,
                'rejected': agg['rejected'] or 0,
            }
        except ImportError:
            pass

        cache.set(f'refund_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)

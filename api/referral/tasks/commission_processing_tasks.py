# api/referral/tasks/commission_processing_tasks.py
# Celery tasks: process pending/held commissions
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.process_held_commissions',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def process_held_commissions(self, dry_run: bool = False):
    """
    Release all commissions whose hold period has expired।
    Runs every hour via Celery beat।

    Schedule example (settings.py):
        'referral-process-held-commissions': {
            'task': 'referral.process_held_commissions',
            'schedule': crontab(minute=0),  # every hour
        }
    """
    try:
        from api.referral.services.CommissionService import CommissionService

        result = CommissionService.release_expired_holds(dry_run=dry_run)

        logger.info(
            f"[Task] process_held_commissions: "
            f"released={result['released']}, "
            f"errors={result['errors']}, "
            f"total_amount={result['total_amount']}, "
            f"dry_run={dry_run}"
        )

        return result

    except Exception as exc:
        logger.error(f"[Task] process_held_commissions failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.process_pending_commissions_to_wallet',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def process_pending_commissions_to_wallet(self):
    """
    Pending commissions (status=pending, no hold) কে wallet এ add করো।
    Edge case handler — normally commissions are processed inline।
    Runs daily via Celery beat।

    Schedule example:
        'referral-process-pending-commissions': {
            'task': 'referral.process_pending_commissions_to_wallet',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        }
    """
    try:
        from api.referral.models import CommissionLog
        from api.referral.services.CommissionService import CommissionService
        from django.db.models import Q

        # Pending commissions that have no hold record (should have been paid)
        orphaned = CommissionLog.objects.filter(
            status='pending',
            hold__isnull=True,
            wallet_transaction_id='',
        ).select_related('user', 'referred_user')[:200]

        processed = 0
        errors = 0

        for log in orphaned:
            try:
                from api.wallet.services import WalletService
                from api.wallet.models import Wallet

                wallet, _ = Wallet.objects.get_or_create(user=log.user)
                wallet_txn = WalletService.add_earnings(
                    wallet=wallet,
                    amount=log.amount,
                    description=(
                        f"Level {log.level} referral commission "
                        f"(from {log.referred_user.username})"
                    ),
                    source_type='referral_commission',
                    source_id=str(log.referred_user.id),
                )

                log.status = 'released'
                log.wallet_transaction_id = str(
                    getattr(wallet_txn, 'walletTransaction_id', '')
                )
                log.save(update_fields=['status', 'wallet_transaction_id'])
                processed += 1

            except Exception as e:
                logger.error(
                    f"Failed to process orphaned commission {log.id}: {e}"
                )
                errors += 1

        logger.info(
            f"[Task] process_pending_commissions_to_wallet: "
            f"processed={processed}, errors={errors}"
        )

        return {'processed': processed, 'errors': errors}

    except Exception as exc:
        logger.error(
            f"[Task] process_pending_commissions_to_wallet failed: {exc}"
        )
        raise self.retry(exc=exc)
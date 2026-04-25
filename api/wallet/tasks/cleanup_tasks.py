# api/wallet/tasks/cleanup_tasks.py
"""
Maintenance and cleanup tasks — remove stale data, expired keys, old logs.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.cleanup")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.cleanup_idempotency_keys")
def cleanup_idempotency_keys(self):
    """
    Delete expired idempotency keys.
    Runs daily at 4 AM.
    """
    try:
        from ..services import IdempotencyService
        count = IdempotencyService.cleanup()
        logger.info(f"Cleaned {count} idempotency keys")
        return {"deleted": count}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.cleanup_old_webhook_logs")
def cleanup_old_webhook_logs(self, days: int = 30):
    """
    Delete processed webhook logs older than N days.
    Runs weekly on Sunday at 4 AM.
    """
    try:
        from ..models import WalletWebhookLog
        cutoff = timezone.now() - timedelta(days=days)
        count, _ = WalletWebhookLog.objects.filter(
            is_processed=True,
            processed_at__lt=cutoff,
        ).delete()
        logger.info(f"Cleaned {count} old webhook logs (>{days}d)")
        return {"deleted": count}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.cleanup_expired_sessions")
def cleanup_expired_sessions(self):
    """
    Clean up expired balance reserves and locks.
    Runs daily at 5 AM.
    """
    try:
        from ..models import BalanceReserve, BalanceLock
        now = timezone.now()

        # Expired reserves
        expired_reserves = BalanceReserve.objects.filter(
            status="active", expires_at__lt=now
        )
        reserve_count = 0
        for r in expired_reserves:
            try:
                r.status = "expired"
                r.save(update_fields=["status"])
                # Restore reserved balance
                r.wallet.reserved_balance = max(
                    r.wallet.reserved_balance - r.reserved_amount, __import__("decimal").Decimal("0")
                )
                r.wallet.save(update_fields=["reserved_balance","updated_at"])
                reserve_count += 1
            except Exception as e:
                logger.error(f"Reserve cleanup r={r.reserve_id}: {e}")

        # Expired balance locks
        expired_locks = BalanceLock.objects.filter(
            status="active", expires_at__lt=now
        )
        lock_count = 0
        for lk in expired_locks:
            try:
                lk.status = "expired"
                lk.save(update_fields=["status"])
                lock_count += 1
            except Exception as e:
                logger.error(f"Lock cleanup lk={lk.lock_id}: {e}")

        logger.info(f"Cleanup: {reserve_count} reserves, {lock_count} locks expired")
        return {"reserves_expired": reserve_count, "locks_expired": lock_count}
    except Exception as e:
        raise self.retry(exc=e)

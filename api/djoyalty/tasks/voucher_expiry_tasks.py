# api/djoyalty/tasks/voucher_expiry_tasks.py
"""
Celery task: Daily voucher expiry processing।
Schedule: Daily at 00:30।
"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.expire_vouchers', bind=True, max_retries=3)
def expire_vouchers_task(self):
    """
    Validity শেষ হয়ে যাওয়া active vouchers কে 'expired' status এ নিয়ে যাও।
    Returns: count of expired vouchers
    """
    try:
        from django.utils import timezone
        from ..models.redemption import Voucher

        count = Voucher.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__lt=timezone.now(),
        ).update(status='expired')

        logger.info('[djoyalty] Vouchers expired: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] expire_vouchers error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.expire_gift_cards', bind=True, max_retries=3)
def expire_gift_cards_task(self):
    """
    Validity শেষ হয়ে যাওয়া active gift cards কে 'expired' করো।
    Returns: count of expired gift cards
    """
    try:
        from django.utils import timezone
        from ..models.redemption import GiftCard

        count = GiftCard.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__lt=timezone.now(),
        ).update(status='expired')

        logger.info('[djoyalty] Gift cards expired: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] expire_gift_cards error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc

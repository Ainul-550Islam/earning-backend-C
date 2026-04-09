# api/djoyalty/tasks/subscription_tasks.py
"""
Celery task: Loyalty subscription renewal check।
Schedule: Daily।
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


@shared_task(name='djoyalty.process_subscription_renewals', bind=True, max_retries=3)
def process_subscription_renewals_task(self):
    """
    Due loyalty subscriptions process করো — bonus points দাও এবং next renewal set করো।
    Returns: count of processed renewals
    """
    try:
        from ..services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService

        count = SubscriptionLoyaltyService.process_monthly_renewals()
        logger.info('[djoyalty] Subscription renewals processed: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] process_subscription_renewals error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.cancel_expired_subscriptions', bind=True, max_retries=3)
def cancel_expired_subscriptions_task(self):
    """
    Payment fail হওয়া বা manually cancelled subscriptions deactivate করো।
    Returns: count of deactivated subscriptions
    """
    try:
        from django.utils import timezone
        from ..models.advanced import LoyaltySubscription

        # Subscriptions যাদের next_renewal overdue (7 দিন grace period)
        from datetime import timedelta
        grace_cutoff = timezone.now() - timedelta(days=7)

        overdue = LoyaltySubscription.objects.filter(
            is_active=True,
            next_renewal_at__isnull=False,
            next_renewal_at__lt=grace_cutoff,
        )
        count = overdue.update(is_active=False, cancelled_at=timezone.now())
        if count:
            logger.warning('[djoyalty] Cancelled %d overdue subscriptions', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] cancel_expired_subscriptions error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc

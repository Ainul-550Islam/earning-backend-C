# api/djoyalty/tasks/earn_rule_tasks.py
"""
Celery task: Bulk earn rule processing — deactivate expired rules।
Schedule: Daily cron।
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


@shared_task(name='djoyalty.deactivate_expired_earn_rules', bind=True, max_retries=3)
def deactivate_expired_earn_rules_task(self):
    """
    Validity period শেষ হয়ে যাওয়া earn rules deactivate করো।
    Returns: count of deactivated rules
    """
    try:
        from django.utils import timezone
        from ..models.earn_rules import EarnRule

        now = timezone.now()
        count = EarnRule.objects.filter(
            is_active=True,
            valid_until__isnull=False,
            valid_until__lt=now,
        ).update(is_active=False)

        logger.info('[djoyalty] Deactivated %d expired earn rules', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] deactivate_expired_earn_rules error: %s', exc)
        raise self.retry(exc=exc, countdown=60) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.activate_scheduled_earn_rules', bind=True, max_retries=3)
def activate_scheduled_earn_rules_task(self):
    """
    valid_from date পৌঁছে গেছে এমন earn rules activate করো।
    Returns: count of activated rules
    """
    try:
        from django.utils import timezone
        from ..models.earn_rules import EarnRule

        now = timezone.now()
        count = EarnRule.objects.filter(
            is_active=False,
            valid_from__isnull=False,
            valid_from__lte=now,
            valid_until__isnull=True,
        ).update(is_active=True)

        scheduled_count = EarnRule.objects.filter(
            is_active=False,
            valid_from__isnull=False,
            valid_from__lte=now,
            valid_until__gt=now,
        ).update(is_active=True)

        total = count + scheduled_count
        logger.info('[djoyalty] Activated %d scheduled earn rules', total)
        return total

    except Exception as exc:
        logger.error('[djoyalty] activate_scheduled_earn_rules error: %s', exc)
        raise self.retry(exc=exc, countdown=60) if hasattr(self, 'retry') else exc

# api/djoyalty/tasks/streak_reset_tasks.py
"""Midnight: broken streak check এবং reset।"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func: return func
        return lambda f: f

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.check_broken_streaks', bind=True, max_retries=3, default_retry_delay=30)
def check_broken_streaks_task(self):
    """Midnight: continuous activity না থাকা streaks deactivate করো।"""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from ..models.engagement import DailyStreak

        yesterday = timezone.now().date() - timedelta(days=1)
        broken = DailyStreak.objects.filter(
            is_active=True,
            last_activity_date__lt=yesterday,
        ).exclude(last_activity_date__isnull=True)
        count = broken.update(is_active=False)
        logger.info('[djoyalty] Broken streaks reset: %d', count)
        return count
    except Exception as exc:
        logger.error('[djoyalty] check_broken_streaks error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.reset_all_daily_streaks', bind=True, max_retries=3, default_retry_delay=30)
def reset_all_daily_streaks_task(self):
    """Weekly: orphaned streak records cleanup।"""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from ..models.engagement import DailyStreak

        old_cutoff = timezone.now() - timedelta(days=90)
        count = DailyStreak.objects.filter(
            is_active=False,
            updated_at__lt=old_cutoff,
            current_streak=0,
        ).count()
        logger.info('[djoyalty] Old inactive streaks: %d', count)
        return count
    except Exception as exc:
        logger.error('[djoyalty] reset_all_daily_streaks error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc

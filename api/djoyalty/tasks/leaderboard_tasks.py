# api/djoyalty/tasks/leaderboard_tasks.py
"""
Celery task: Hourly leaderboard refresh।
Schedule: Every hour।
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


@shared_task(name='djoyalty.refresh_leaderboard', bind=True, max_retries=3)
def refresh_leaderboard_task(self):
    """
    Top customers leaderboard refresh করো।
    Cache update করে যাতে API fast থাকে।
    Returns: count of entries in leaderboard
    """
    try:
        from ..services.engagement.LeaderboardService import LeaderboardService

        top_customers = list(LeaderboardService.get_top_customers(limit=100))
        count = len(top_customers)

        logger.info('[djoyalty] Leaderboard refreshed: %d entries', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] refresh_leaderboard error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.refresh_monthly_leaderboard', bind=True, max_retries=3)
def refresh_monthly_leaderboard_task(self):
    """
    Monthly leaderboard (এই মাসে সবচেয়ে বেশি earn করেছে)।
    Returns: count of entries
    """
    try:
        from ..services.engagement.LeaderboardService import LeaderboardService

        monthly = list(LeaderboardService.get_top_customers(limit=50, period='monthly'))
        count = len(monthly)

        logger.info('[djoyalty] Monthly leaderboard refreshed: %d entries', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] refresh_monthly_leaderboard error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc

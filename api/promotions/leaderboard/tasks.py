# promotions/leaderboard/tasks.py
from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task
def refresh_leaderboard_cache():
    """Refresh all leaderboard caches every 5 mins."""
    from api.promotions.leaderboard.publisher_leaderboard import PublisherLeaderboard
    lb = PublisherLeaderboard()
    refreshed = 0
    for period in ['daily', 'weekly', 'monthly']:
        try:
            lb.get_leaderboard(period=period, limit=50)
            refreshed += 1
        except Exception as e:
            logger.error(f'Leaderboard refresh failed [{period}]: {e}')
    return {'refreshed': refreshed}

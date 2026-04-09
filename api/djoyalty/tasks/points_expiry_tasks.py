# api/djoyalty/tasks/points_expiry_tasks.py
"""Daily cron: expire points এবং expiry warnings পাঠাও।"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func: return func
        return lambda f: f

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.expire_points', bind=True, max_retries=3, default_retry_delay=60)
def expire_points_task(self):
    """Daily: মেয়াদ শেষ হওয়া points deduct করো।"""
    try:
        from ..services.points.PointsExpiryService import PointsExpiryService
        count = PointsExpiryService.process_expired_points()
        logger.info('[djoyalty] Expired points processed: %d records', count)
        return count
    except Exception as exc:
        logger.error('[djoyalty] expire_points error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.send_expiry_warnings', bind=True, max_retries=3, default_retry_delay=60)
def send_expiry_warnings_task(self):
    """Daily: আসন্ন expiry warning notifications পাঠাও।"""
    try:
        from ..services.points.PointsExpiryService import PointsExpiryService
        count = PointsExpiryService.send_expiry_warnings()
        logger.info('[djoyalty] Expiry warnings sent: %d', count)
        return count
    except Exception as exc:
        logger.error('[djoyalty] send_expiry_warnings error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc

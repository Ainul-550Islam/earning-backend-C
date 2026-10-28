# api/admin_panel/tasks/activity_cleanup_tasks.py
"""Cleanup old admin activity logs."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def run_cleanup():
    """Delete activity logs older than ACTIVITY_LOG_RETENTION_DAYS."""
    from ..constants import ACTIVITY_LOG_RETENTION_DAYS, SEARCH_HISTORY_RETENTION_DAYS
    results = {}

    try:
        from ..models.activity import AdminActivity
        cutoff = timezone.now() - timedelta(days=ACTIVITY_LOG_RETENTION_DAYS)
        deleted, _ = AdminActivity.objects.filter(created_at__lt=cutoff).delete()
        results['admin_activity_deleted'] = deleted
        logger.info(f"Cleaned up {deleted} old AdminActivity records.")
    except Exception as e:
        logger.error(f"AdminActivity cleanup error: {e}")
        results['admin_activity_error'] = str(e)

    try:
        from ..models.activity import AdminSearch
        cutoff = timezone.now() - timedelta(days=SEARCH_HISTORY_RETENTION_DAYS)
        deleted, _ = AdminSearch.objects.filter(created_at__lt=cutoff).delete()
        results['admin_search_deleted'] = deleted
        logger.info(f"Cleaned up {deleted} old AdminSearch records.")
    except Exception as e:
        logger.error(f"AdminSearch cleanup error: {e}")

    return results


@shared_task(name='admin_panel.tasks.activity_cleanup_tasks.cleanup_old_activity_task')
def cleanup_old_activity_task():
    return run_cleanup()
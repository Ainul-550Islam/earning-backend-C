# api/cms/tasks/redirect_cleanup_tasks.py
"""Remove unused redirects task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.cleanup_unused_redirects', bind=True)
def cleanup_unused_redirects(self, days: int = 90):
    """Remove redirects with no hits in last N days."""
    try:
        from api.cms.services_new.RedirectService import RedirectService
        deleted = RedirectService.cleanup_unused(days=days)
        logger.info(f"[Task] Deleted {deleted} unused redirects")
        return {'status': 'success', 'deleted': deleted}
    except Exception as exc:
        logger.error(f"[Task] Redirect cleanup failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.cleanup_expired_redirects', bind=True)
def cleanup_expired_redirects(self):
    """Deactivate expired redirects."""
    try:
        from api.cms.services_new.RedirectService import RedirectService
        count = RedirectService.cleanup_expired()
        logger.info(f"[Task] Deactivated {count} expired redirects")
        return {'status': 'success', 'deactivated': count}
    except Exception as exc:
        logger.error(f"[Task] Expired redirect cleanup failed: {exc}", exc_info=True)
        raise

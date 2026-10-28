# api/cms/tasks/popup_stats_tasks.py
"""Daily popup analytics aggregation."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.aggregate_popup_stats', bind=True)
def aggregate_popup_stats(self):
    """Aggregate daily popup statistics."""
    try:
        from api.cms.services_new.PopupService import PopupService
        count = PopupService.aggregate_daily_stats()
        logger.info(f"[Task] Popup stats aggregated for {count} popups")
        return {'status': 'success', 'popups_processed': count}
    except Exception as exc:
        logger.error(f"[Task] Popup stats aggregation failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.cleanup_old_popup_stats', bind=True)
def cleanup_old_popup_stats(self, days: int = 90):
    """Remove popup stats older than N days."""
    try:
        from api.cms.models_new.popup import PopupStat
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        deleted, _ = PopupStat.objects.filter(date__lt=cutoff).delete()
        logger.info(f"[Task] Deleted {deleted} old popup stat records")
        return {'status': 'success', 'deleted': deleted}
    except Exception as exc:
        logger.error(f"[Task] Popup stat cleanup failed: {exc}", exc_info=True)
        raise

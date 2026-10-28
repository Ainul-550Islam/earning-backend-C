# api/admin_panel/tasks/session_cleanup_tasks.py
"""Cleanup stale admin sessions."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def run_session_cleanup():
    """Mark admin sessions as expired if last_seen is older than SESSION_RETENTION_DAYS."""
    from ..constants import SESSION_RETENTION_DAYS
    results = {}

    try:
        from ..models.activity import AdminSession
        now = timezone.now()
        stale_cutoff = now - timedelta(hours=24)      # sessions idle > 24h → expired
        old_cutoff = now - timedelta(days=SESSION_RETENTION_DAYS)  # sessions > 30d → delete

        # Mark stale sessions as expired
        expired_count = AdminSession.objects.filter(
            is_active=True,
            last_seen__lt=stale_cutoff
        ).update(is_active=False, status='expired', ended_at=now)
        results['expired'] = expired_count

        # Delete very old sessions
        deleted, _ = AdminSession.objects.filter(
            is_active=False,
            started_at__lt=old_cutoff
        ).delete()
        results['deleted'] = deleted

        logger.info(f"Session cleanup: {expired_count} expired, {deleted} deleted.")
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")
        results['error'] = str(e)

    return results


@shared_task(name='admin_panel.tasks.session_cleanup_tasks.cleanup_stale_sessions_task')
def cleanup_stale_sessions_task():
    return run_session_cleanup()
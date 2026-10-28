# api/admin_panel/tasks/maintenance_tasks.py
"""Pre/post maintenance notification tasks."""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_pre_maintenance_notification(window_id: int):
    """Send advance warning email to all active users before maintenance."""
    try:
        from ..models.config import MaintenanceWindow
        window = MaintenanceWindow.objects.get(pk=window_id)
        if not window.notify_users:
            return {'skipped': True, 'reason': 'notify_users=False'}

        from django.contrib.auth import get_user_model
        User = get_user_model()
        active_users = User.objects.filter(is_active=True).exclude(email='')
        emails = list(active_users.values_list('email', flat=True)[:5000])

        from ..utils import send_admin_email_notification
        subject = f"Scheduled Maintenance: {window.title}"
        body = (
            f"Dear User,\n\n"
            f"We will be performing maintenance on {window.start_at.strftime('%Y-%m-%d %H:%M UTC')}.\n"
            f"Expected duration: {window.duration_minutes} minutes.\n\n"
            f"{window.message}\n\n"
            f"Thank you for your patience."
        )
        # Send in batches of 100
        for i in range(0, len(emails), 100):
            batch = emails[i:i + 100]
            try:
                send_admin_email_notification(subject, body, batch)
            except Exception as e:
                logger.error(f"Maintenance notification batch failed: {e}")

        logger.info(f"Maintenance notification sent to {len(emails)} users for window {window_id}.")
        return {'success': True, 'notified': len(emails)}
    except Exception as e:
        logger.error(f"send_pre_maintenance_notification failed: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='admin_panel.tasks.maintenance_tasks.send_pre_maintenance_notification_task')
def send_pre_maintenance_notification_task(window_id: int):
    return send_pre_maintenance_notification(window_id)


@shared_task(name='admin_panel.tasks.maintenance_tasks.auto_activate_maintenance_windows')
def auto_activate_maintenance_windows():
    """Automatically activate/deactivate maintenance windows based on schedule."""
    try:
        from ..models.config import MaintenanceWindow
        from django.core.cache import cache
        from django.db.models import Q
        now = timezone.now()

        # Activate due windows
        due = MaintenanceWindow.objects.filter(
            is_active=False,
            start_at__lte=now,
            end_at__gte=now,
        )
        for w in due:
            w.is_active = True
            w.save(update_fields=['is_active'])

        # Deactivate expired windows
        expired = MaintenanceWindow.objects.filter(
            is_active=True,
            end_at__lt=now,
        )
        for w in expired:
            w.is_active = False
            w.save(update_fields=['is_active'])
            cache.delete('admin_panel:maintenance_mode_active')

        logger.info(f"Auto-maintenance: activated {due.count()}, deactivated {expired.count()} windows.")
        return {'activated': due.count(), 'deactivated': expired.count()}
    except Exception as e:
        logger.error(f"auto_activate_maintenance_windows failed: {e}")
        return {'error': str(e)}
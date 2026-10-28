# api/admin_panel/tasks/system_health_tasks.py
"""System health check tasks."""
import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def run_health_check():
    """Run all system health checks and cache the result."""
    from ..utils import get_full_system_health
    health = get_full_system_health()
    cache.set('admin_panel:system_health', health, 60)
    if health['overall'] != 'healthy':
        logger.warning(f"System health degraded: {health}")
        _notify_admins_of_health_issue(health)
    else:
        logger.debug(f"System health OK: {health['overall']}")
    return health


def _notify_admins_of_health_issue(health: dict):
    """Send alert to superadmins when system health is degraded/down."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_superuser=True, is_active=True).exclude(email='')
        emails = list(admins.values_list('email', flat=True))
        if not emails:
            return
        from ..utils import send_admin_email_notification
        failing = [k for k, v in health['checks'].items() if v['status'] != 'healthy']
        subject = f"[ALERT] System Health: {health['overall'].upper()} — {', '.join(failing)}"
        body = (
            f"System health check at {health['checked_at']} detected issues:\n\n"
            + '\n'.join(f"  - {k}: {v['status']} {v.get('error', '')}" for k, v in health['checks'].items())
            + "\n\nPlease investigate immediately."
        )
        send_admin_email_notification(subject, body, emails)
    except Exception as e:
        logger.error(f"Health alert email failed: {e}")


@shared_task(name='admin_panel.tasks.system_health_tasks.run_health_check_task')
def run_health_check_task():
    return run_health_check()
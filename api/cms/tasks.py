# api/cms/tasks.py
"""Main CMS Celery tasks — general CMS tasks."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.run_health_check')
def run_health_check():
    try:
        from api.cms.INTEGRATION_SYSTEM.health_check import HealthChecker
    except ImportError:
        HealthChecker = None
    from django.core.cache import cache
    if HealthChecker is None:
        return 'unavailable'
    report = HealthChecker.check_all()
    cache.set('cms_health_report', report, 60)
    if report.get('status') == 'fail':
        logger.error(f"[Health] FAILED: {report}")
    return report.get('status', 'unknown')


@shared_task(name='cms.tasks.process_scheduled_content')
def process_scheduled_content():
    from api.cms.services_new.ContentCalendarService import ContentCalendarService
    count = ContentCalendarService.process_due_schedules()
    return f"Published {count} scheduled items"


@shared_task(name='cms.tasks.cleanup_audit_logs')
def cleanup_audit_logs(days=365):
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog
    except ImportError:
        pass
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = IntegrationAuditLog.objects.filter(created_at__lt=cutoff).delete()
    return f"Deleted {deleted} old audit logs"


@shared_task(name='cms.tasks.cleanup_form_submissions')
def cleanup_form_submissions(days=180):
    from api.cms.models_new.forms import FormSubmission
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = FormSubmission.objects.filter(submitted_at__lt=cutoff).delete()
    return f"Deleted {deleted} old form submissions"


@shared_task(name='cms.tasks.send_pending_notifications')
def send_pending_notifications():
    try:
        from api.cms.models_new.extras import Notification
        pending = Notification.objects.filter(
            is_read=False, email_sent=False
        ).select_related('user')[:100]
        sent = 0
        for notif in pending:
            try:
                from api.cms.services_new.NotificationService import NotificationService
                NotificationService.send_email_notification(notif)
                sent += 1
            except Exception:
                pass
        return f"Sent {sent} notifications"
    except Exception as e:
        logger.error(f"[Tasks] notification send failed: {e}")


@shared_task(name='cms.tasks.update_user_levels')
def update_user_levels():
    """Recalculate levels for all users based on earnings."""
    from api.cms.services_new.WithdrawalService import UserProfileService
    from api.cms.models_new.withdrawal import UserProfile
    profiles = UserProfile.objects.all()
    updated = 0
    for profile in profiles:
        try:
            old = profile.level
            new = UserProfileService.update_level(profile.user)
            if old != new:
                updated += 1
        except Exception:
            pass
    return f"Updated {updated} user levels"


@shared_task(name='cms.tasks.ping_integration_services')
def ping_integration_services():
    try:
        from api.cms.INTEGRATION_SYSTEM.integ_registry import CMSRegistry
    except ImportError:
        pass
    status = CMSRegistry.status()
    return f"Registry: {status['services']} services registered"


@shared_task(name='cms.tasks.reset_performance_stats')
def reset_performance_stats():
    logger.info("[Tasks] Performance stats reset (cache auto-expires)")
    return "done"


@shared_task(name='cms.tasks.cleanup_stale_locks')
def cleanup_stale_locks():
    try:
        from api.cms.INTEGRATION_SYSTEM.sync_manager import SyncManager
    except ImportError:
        pass
    logger.info("[Tasks] Stale sync locks cleanup (cache auto-expires)")
    return "done"


@shared_task(name='cms.tasks.generate_sitemap')
def generate_sitemap():
    try:
        from api.cms.services_new.SEOService import SEOService
        SEOService.rebuild_sitemap()
        return "Sitemap regenerated"
    except Exception as e:
        return f"Sitemap error: {e}"


@shared_task(name='cms.tasks.expire_withdrawal_pending')
def expire_old_pending_withdrawals(days=30):
    """Cancel withdrawals stuck in pending for too long."""
    from api.cms.models_new.withdrawal import WithdrawalRequest
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=days)
    count = WithdrawalRequest.objects.filter(
        status='pending', created_at__lt=cutoff
    ).update(status='cancelled')
    return f"Cancelled {count} stale withdrawal requests"

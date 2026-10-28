# api/admin_panel/signals/maintenance_signals.py
"""Signals: on MaintenanceWindow save → notify users if needed."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.MaintenanceWindow')
def on_maintenance_window_change(sender, instance, created, **kwargs):
    """Sync cache and schedule pre-notification."""
    from django.utils import timezone
    now = timezone.now()

    if instance.is_currently_active:
        end_ts = instance.end_at
        ttl = max(60, int((end_ts - now).total_seconds()) + 120) if end_ts else 3600
        cache.set('admin_panel:maintenance_mode_active', True, ttl)
        cache.set('admin_panel:maintenance_message', instance.message, 3600)
        logger.warning(f"Maintenance ACTIVE: {instance.title}")
    else:
        # Only clear if no other active window exists
        try:
            from ..models.config import MaintenanceWindow as MW
            if not MW.objects.filter(is_active=True).exclude(pk=instance.pk).exists():
                cache.delete('admin_panel:maintenance_mode_active')
        except Exception:
            pass

    # Schedule pre-notification if newly created and notify_users=True
    if created and instance.notify_users and instance.start_at > now:
        notify_at = instance.start_at - timezone.timedelta(minutes=instance.notify_before_minutes)
        if notify_at > now:
            try:
                from ..tasks import notify_pre_maintenance
                eta_seconds = int((notify_at - now).total_seconds())
                notify_pre_maintenance.apply_async(
                    args=[instance.pk],
                    countdown=eta_seconds,
                )
                logger.info(f"Scheduled pre-maintenance notification in {eta_seconds}s for window {instance.pk}")
            except Exception as e:
                logger.error(f"Could not schedule pre-maintenance notification: {e}")


@receiver(post_delete, sender='admin_panel.MaintenanceWindow')
def on_maintenance_window_delete(sender, instance, **kwargs):
    """Clear maintenance cache when window is deleted."""
    try:
        from ..models.config import MaintenanceWindow as MW
        if not MW.objects.filter(is_active=True).exists():
            cache.delete('admin_panel:maintenance_mode_active')
    except Exception:
        cache.delete('admin_panel:maintenance_mode_active')
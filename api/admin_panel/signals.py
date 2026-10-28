from typing import Optional, Any, List, Dict
# api/admin_panel/signals.py
"""
Production-ready signals for api.admin_panel.
Keeps all existing signal logic + connects all sub-module signal handlers.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def connect_all_signals():
    """
    Connect all admin_panel signal handlers.
    Called from apps.py AppConfig.ready().
    """
    sub_signals = [
        'activity_signals',
        'config_signals',
        'feature_flag_signals',
        'maintenance_signals',
        'report_signals',
        'session_signals',
        'endpoint_toggle_signals',
    ]
    for name in sub_signals:
        try:
            import importlib
            importlib.import_module(f'.signals.{name}', package='api.admin_panel')
        except ImportError:
            logger.debug(f"Signal module not yet available: {name}")
        except Exception as e:
            logger.warning(f"Error loading signal module {name}: {e}")


# ==================== SystemSettings Signals ====================

@receiver(post_save, sender='admin_panel.SystemSettings')
def on_system_settings_saved(sender, instance, created, **kwargs):
    """Clear system settings cache whenever settings are saved."""
    from django.core.cache import cache
    cache.delete('system_settings')
    cache.delete('admin_panel:system_settings')
    # Also sync maintenance mode cache
    if hasattr(instance, 'maintenance_mode'):
        if instance.maintenance_mode:
            cache.set('admin_panel:maintenance_mode_active', True, 3600)
            cache.set('admin_panel:maintenance_message', instance.maintenance_message, 3600)
        else:
            cache.delete('admin_panel:maintenance_mode_active')
    logger.debug("SystemSettings cache cleared.")


# ==================== SiteNotification Signals ====================

@receiver(post_save, sender='admin_panel.SiteNotification')
def on_site_notification_saved(sender, instance, created, **kwargs):
    """Clear notification cache on save."""
    from django.core.cache import cache
    cache.delete('admin_panel:active_notifications')
    cache.delete('admin_panel:login_notifications')


@receiver(post_delete, sender='admin_panel.SiteNotification')
def on_site_notification_deleted(sender, instance, **kwargs):
    """Clear notification cache on delete."""
    from django.core.cache import cache
    cache.delete('admin_panel:active_notifications')
    cache.delete('admin_panel:login_notifications')


# ==================== SiteContent Signals ====================

@receiver(post_save, sender='admin_panel.SiteContent')
def on_site_content_saved(sender, instance, created, **kwargs):
    """Clear site content cache on save."""
    from django.core.cache import cache
    if instance.identifier:
        cache.delete(f'admin_panel:site_content:{instance.identifier}')
    cache.delete('admin_panel:site_contents_all')


@receiver(post_delete, sender='admin_panel.SiteContent')
def on_site_content_deleted(sender, instance, **kwargs):
    """Clear site content cache on delete."""
    from django.core.cache import cache
    if instance.identifier:
        cache.delete(f'admin_panel:site_content:{instance.identifier}')
    cache.delete('admin_panel:site_contents_all')


# ==================== EndpointToggle Signals ====================

@receiver(post_save, sender='admin_panel.EndpointToggle')
def on_endpoint_toggle_saved(sender, instance, created, **kwargs):
    """Clear endpoint toggle cache and log the change."""
    from django.core.cache import cache
    cache.delete(f'endpoint_toggle_{instance.path}_{instance.method}')
    cache.delete(f'endpoint_toggle_{instance.path}_ALL')
    cache.delete('admin_panel:endpoint_toggles')
    status = 'enabled' if instance.is_enabled else 'disabled'
    logger.info(f"EndpointToggle: [{instance.method}] {instance.path} → {status}")


# ==================== SystemConfig Signals ====================

@receiver(post_save, sender='admin_panel.SystemConfig')
def on_system_config_saved(sender, instance, created, **kwargs):
    """Clear config cache when a SystemConfig is saved."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:config:{instance.key}')
    cache.delete('admin_panel:config_all')
    logger.debug(f"SystemConfig cache cleared for key: {instance.key}")


@receiver(post_delete, sender='admin_panel.SystemConfig')
def on_system_config_deleted(sender, instance, **kwargs):
    """Clear config cache when a SystemConfig is deleted."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:config:{instance.key}')
    cache.delete('admin_panel:config_all')


# ==================== FeatureFlag Signals ====================

@receiver(post_save, sender='admin_panel.FeatureFlag')
def on_feature_flag_saved(sender, instance, created, **kwargs):
    """Clear feature flag cache when a flag is saved."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')
    cache.delete('admin_panel:feature_flags')
    status = 'enabled' if instance.is_enabled else 'disabled'
    logger.info(f"FeatureFlag '{instance.flag_key}' → {status} ({instance.rollout_pct}% rollout)")


@receiver(post_delete, sender='admin_panel.FeatureFlag')
def on_feature_flag_deleted(sender, instance, **kwargs):
    """Clear feature flag cache when deleted."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')
    cache.delete('admin_panel:feature_flags')


# ==================== MaintenanceWindow Signals ====================

@receiver(post_save, sender='admin_panel.MaintenanceWindow')
def on_maintenance_window_saved(sender, instance, created, **kwargs):
    """Sync maintenance mode cache when a window is saved."""
    from django.core.cache import cache
    from django.utils import timezone
    now = timezone.now()

    if instance.is_currently_active:
        end_ts = instance.end_at
        ttl = max(60, int((end_ts - now).total_seconds()) + 120) if end_ts else 3600
        cache.set('admin_panel:maintenance_mode_active', True, ttl)
        cache.set('admin_panel:maintenance_message', instance.message, 3600)
        logger.warning(f"Maintenance window ACTIVATED: {instance.title}")
    else:
        # Only clear if no other window is currently active
        try:
            from .models.config import MaintenanceWindow
            still_active = MaintenanceWindow.objects.filter(
                is_active=True
            ).exclude(pk=instance.pk).exists()
            if not still_active:
                cache.delete('admin_panel:maintenance_mode_active')
        except Exception:
            pass


@receiver(post_delete, sender='admin_panel.MaintenanceWindow')
def on_maintenance_window_deleted(sender, instance, **kwargs):
    """Clear maintenance cache when a window is deleted."""
    from django.core.cache import cache
    try:
        from .models.config import MaintenanceWindow
        still_active = MaintenanceWindow.objects.filter(is_active=True).exists()
        if not still_active:
            cache.delete('admin_panel:maintenance_mode_active')
    except Exception:
        cache.delete('admin_panel:maintenance_mode_active')


# ==================== ReportExport Signals ====================

@receiver(post_save, sender='admin_panel.ReportExport')
def on_report_export_completed(sender, instance, created, **kwargs):
    """When a report export is completed, notify the requester via email."""
    if instance.status == 'completed' and not created:
        try:
            from .services.AdminNotificationService import AdminNotificationService
            if instance.generated_by and instance.generated_by.email:
                AdminNotificationService.notify_report_ready(instance)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Failed to notify report ready: {e}")


# ==================== AdminProfile Signals ====================

@receiver(post_save, sender='admin_panel.AdminProfile')
def on_admin_profile_saved(sender, instance, created, **kwargs):
    """Log admin profile creation."""
    if created:
        logger.info(f"AdminProfile created for user: {instance.user.username} (role={instance.role})")


# ==================== DashboardLayout Signals ====================

@receiver(post_save, sender='admin_panel.DashboardLayout')
def on_dashboard_layout_saved(sender, instance, created, **kwargs):
    """Clear dashboard layout cache."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:dashboard_layout:{instance.user_id}')


# ==================== EmailTemplate Signals ====================

@receiver(post_save, sender='admin_panel.EmailTemplate')
def on_email_template_saved(sender, instance, created, **kwargs):
    """Clear email template cache."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:email_template:{instance.key}')


@receiver(post_delete, sender='admin_panel.EmailTemplate')
def on_email_template_deleted(sender, instance, **kwargs):
    """Clear email template cache on delete."""
    from django.core.cache import cache
    cache.delete(f'admin_panel:email_template:{instance.key}')
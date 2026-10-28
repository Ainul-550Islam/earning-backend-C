# api/admin_panel/receivers.py
"""
Signal receivers for admin_panel.
All signal connections in one place — clean architecture.
"""
import logging
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.cache import cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.SystemConfig')
def on_system_config_saved(sender, instance, created, **kwargs):
    """Clear config cache when SystemConfig changes."""
    cache.delete(f'admin_panel:config:{instance.key}')
    cache.delete(f'admin_panel:config_group:{instance.group}')
    cache.delete('admin_panel:config_all')
    # Fire integration event
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('system.config_updated', {
            'config_key': instance.key,
            'group': instance.group,
            'value': instance.value,
        }, source='admin_panel')
    except Exception:
        pass


@receiver(post_save, sender='admin_panel.FeatureFlag')
def on_feature_flag_saved(sender, instance, **kwargs):
    """Clear feature flag cache on change."""
    cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')
    cache.delete('admin_panel:feature_flags_all')
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish('system.feature_flag_changed', {
            'flag_key': instance.flag_key,
            'is_enabled': instance.is_enabled,
            'rollout_pct': instance.rollout_pct,
        }, source='admin_panel')
    except Exception:
        pass


@receiver(post_save, sender='admin_panel.MaintenanceWindow')
def on_maintenance_window_saved(sender, instance, **kwargs):
    """Update maintenance cache when window changes."""
    if instance.is_active:
        cache.set('admin_panel:maintenance_mode_active', True, 86400)
        cache.set('admin_panel:maintenance_message', instance.message, 86400)
    else:
        cache.delete('admin_panel:maintenance_mode_active')


@receiver(user_logged_in)
def on_admin_login(sender, request, user, **kwargs):
    """Create AdminSession on staff login."""
    if not user.is_staff:
        return
    try:
        from api.admin_panel.models.activity import AdminSession, AdminActivity
        session_key = request.session.session_key or 'no-session'
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()

        AdminSession.objects.get_or_create(
            user=user,
            session_key=session_key,
            defaults={
                'ip': ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                'is_active': True,
                'status': 'active',
            }
        )
        AdminActivity.log(
            actor=user, action='admin_login',
            ip=ip,
            method='POST',
            path='/admin/login/',
        )
        # Update AdminProfile last_seen
        try:
            user.admin_profile.last_seen = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now()
            user.admin_profile.save(update_fields=['last_seen'])
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"[receivers] admin_login signal failed: {e}")


@receiver(user_logged_out)
def on_admin_logout(sender, request, user, **kwargs):
    """Mark AdminSession inactive on logout."""
    if not user or not user.is_staff:
        return
    try:
        from api.admin_panel.models.activity import AdminSession
        from django.utils import timezone
        session_key = request.session.session_key or ''
        AdminSession.objects.filter(
            user=user, session_key=session_key, is_active=True
        ).update(is_active=False, status='logged_out', ended_at=timezone.now())
    except Exception as e:
        logger.debug(f"[receivers] admin_logout signal failed: {e}")


@receiver(user_login_failed)
def on_admin_login_failed(sender, credentials, request, **kwargs):
    """Log failed admin login attempts."""
    try:
        from api.admin_panel.models.activity import AdminActivity
        ip = request.META.get('REMOTE_ADDR', '') if request else ''
        AdminActivity.log(
            actor=None,
            action='admin_login_failed',
            changes={'username': credentials.get('username', '')},
            ip=ip,
            status='failed',
        )
    except Exception:
        pass
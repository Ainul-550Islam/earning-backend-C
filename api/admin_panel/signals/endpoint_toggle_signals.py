# api/admin_panel/signals/endpoint_toggle_signals.py
"""Signals: on EndpointToggle save → log activity + clear cache."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.EndpointToggle')
def on_endpoint_toggle_change(sender, instance, created, **kwargs):
    """Clear endpoint toggle cache and log the change."""
    cache.delete(f'endpoint_toggle_{instance.path}_{instance.method}')
    cache.delete(f'endpoint_toggle_{instance.path}_ALL')
    cache.delete('admin_panel:endpoint_toggles')

    status = 'ENABLED' if instance.is_enabled else 'DISABLED'
    action = 'create' if created else 'toggle'
    logger.info(f"EndpointToggle [{action}]: [{instance.method}] {instance.path} → {status}")

    try:
        from ..models.activity import AdminActivity
        AdminActivity.log(
            actor=None,
            action='endpoint_toggle',
            model_name='EndpointToggle',
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes={'is_enabled': instance.is_enabled, 'path': instance.path},
        )
    except Exception as e:
        logger.debug(f"EndpointToggle activity log error: {e}")


@receiver(post_delete, sender='admin_panel.EndpointToggle')
def on_endpoint_toggle_delete(sender, instance, **kwargs):
    """Clear endpoint toggle cache on delete."""
    cache.delete(f'endpoint_toggle_{instance.path}_{instance.method}')
    cache.delete(f'endpoint_toggle_{instance.path}_ALL')
    cache.delete('admin_panel:endpoint_toggles')
    logger.info(f"EndpointToggle deleted: [{instance.method}] {instance.path}")
# api/admin_panel/signals/config_signals.py
"""Signals: on SystemConfig change → clear cache."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.SystemConfig')
def on_system_config_change(sender, instance, created, **kwargs):
    cache.delete(f'admin_panel:config:{instance.key}')
    cache.delete('admin_panel:config_all')
    logger.debug(f"Config cache cleared: {instance.key}")


@receiver(post_delete, sender='admin_panel.SystemConfig')
def on_system_config_delete(sender, instance, **kwargs):
    cache.delete(f'admin_panel:config:{instance.key}')
    cache.delete('admin_panel:config_all')
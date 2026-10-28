# api/admin_panel/signals/feature_flag_signals.py
"""Signals: on FeatureFlag change → clear cache + notify admins."""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender='admin_panel.FeatureFlag')
def on_feature_flag_change(sender, instance, created, **kwargs):
    cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')
    cache.delete('admin_panel:feature_flags')
    action = 'created' if created else ('enabled' if instance.is_enabled else 'disabled')
    logger.info(f"FeatureFlag '{instance.flag_key}' {action} ({instance.rollout_pct}% rollout)")

    # Notify admins of flag changes via async task
    if not created:
        try:
            from ..tasks import evaluate_feature_flag_rollouts
            evaluate_feature_flag_rollouts.delay()
        except Exception:
            pass


@receiver(post_delete, sender='admin_panel.FeatureFlag')
def on_feature_flag_delete(sender, instance, **kwargs):
    cache.delete(f'admin_panel:feature_flag:{instance.flag_key}')
    cache.delete('admin_panel:feature_flags')
    logger.info(f"FeatureFlag '{instance.flag_key}' deleted.")
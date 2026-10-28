# api/admin_panel/tasks/config_cache_tasks.py
"""Refresh system config cache tasks."""
import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


def refresh_all_config():
    """Re-cache all SystemConfig entries."""
    try:
        from ..models.config import SystemConfig
        configs = SystemConfig.objects.all()
        for config in configs:
            typed_value = config.get_typed_value()
            cache.set(f'admin_panel:config:{config.key}', typed_value, 600)
        # Build full config dict cache
        all_config = {c.key: c.get_typed_value() for c in configs}
        cache.set('admin_panel:config_all', all_config, 600)
        logger.info(f"Refreshed {len(configs)} system config cache entries.")
        return {'refreshed': len(list(configs))}
    except Exception as e:
        logger.error(f"Config cache refresh error: {e}")
        return {'error': str(e)}


def refresh_feature_flags():
    """Re-cache all FeatureFlag entries."""
    try:
        from ..models.config import FeatureFlag
        flags = FeatureFlag.objects.all()
        for flag in flags:
            result = flag.is_enabled and flag.rollout_pct > 0
            cache.set(f'admin_panel:feature_flag:{flag.flag_key}', result, 300)
        logger.info(f"Refreshed {len(list(flags))} feature flag cache entries.")
        return {'refreshed_flags': len(list(flags))}
    except Exception as e:
        logger.error(f"Feature flag cache refresh error: {e}")
        return {'error': str(e)}


@shared_task(name='admin_panel.tasks.config_cache_tasks.refresh_config_cache_task')
def refresh_config_cache_task():
    """Celery periodic task — refresh config and feature flag cache."""
    result = refresh_all_config()
    result.update(refresh_feature_flags())
    return result
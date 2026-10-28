# api/admin_panel/tasks/feature_flag_tasks.py
"""Feature flag rollout evaluation tasks."""
import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


def refresh_all_flags():
    """Re-cache all feature flag states."""
    try:
        from ..models.config import FeatureFlag
        flags = list(FeatureFlag.objects.all())
        for flag in flags:
            result = flag.is_enabled and flag.rollout_pct > 0
            cache.set(f'admin_panel:feature_flag:{flag.flag_key}', result, 300)
        all_flags = {f.flag_key: f.is_enabled for f in flags}
        cache.set('admin_panel:feature_flags', all_flags, 300)
        logger.info(f"Feature flags refreshed: {len(flags)} flags.")
        return {'refreshed': len(flags)}
    except Exception as e:
        logger.error(f"Feature flag refresh error: {e}")
        return {'error': str(e)}


@shared_task(name='admin_panel.tasks.feature_flag_tasks.refresh_all_flags_task')
def refresh_all_flags_task():
    return refresh_all_flags()
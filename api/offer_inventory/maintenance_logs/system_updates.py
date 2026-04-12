# api/offer_inventory/maintenance_logs/system_updates.py
"""System Updates — Manage system settings and post-deployment tasks."""
import json
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SystemUpdater:
    """Manage system configuration updates."""

    @staticmethod
    def update_setting(key: str, value: str,
                        value_type: str = 'string',
                        description: str = '',
                        tenant=None) -> object:
        """Update or create a system setting."""
        from api.offer_inventory.models import SystemSetting
        obj, created = SystemSetting.objects.update_or_create(
            key=key, tenant=tenant,
            defaults={
                'value'      : value,
                'value_type' : value_type,
                'description': description,
            }
        )
        cache.delete(f'setting:{key}:{tenant}')
        action = 'Created' if created else 'Updated'
        logger.info(f'{action} system setting: {key}={value[:50]}')
        return obj

    @staticmethod
    def get_setting(key: str, default=None, tenant=None):
        """Get a system setting with caching."""
        from api.offer_inventory.models import SystemSetting
        cache_key = f'setting:{key}:{tenant}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            s   = SystemSetting.objects.get(key=key, tenant=tenant)
            val = s.value
            if s.value_type == 'int':
                val = int(val)
            elif s.value_type == 'bool':
                val = val.lower() in ('true', '1', 'yes')
            elif s.value_type == 'json':
                val = json.loads(val)
            cache.set(cache_key, val, 300)
            return val
        except Exception:
            return default

    @staticmethod
    def bulk_update(settings_dict: dict, tenant=None) -> int:
        """Update multiple settings at once."""
        count = 0
        for key, value in settings_dict.items():
            SystemUpdater.update_setting(key, str(value), tenant=tenant)
            count += 1
        return count

    @staticmethod
    def run_post_deployment():
        """Tasks to run after every deployment."""
        from api.offer_inventory.optimization_scale.query_optimizer import QueryOptimizer
        from api.offer_inventory.system_devops.db_indexer import DBIndexer

        # Warm caches
        QueryOptimizer.warm_offer_cache()
        # Analyze tables
        DBIndexer.analyze_tables()

        logger.info('Post-deployment tasks complete.')
        return {
            'cache_warmed' : True,
            'tables_analyzed': True,
            'completed_at' : timezone.now().isoformat(),
        }

    @staticmethod
    def get_all_settings(tenant=None) -> list:
        """List all system settings."""
        from api.offer_inventory.models import SystemSetting
        qs = SystemSetting.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('key', 'value', 'value_type', 'description', 'is_public')
            .order_by('key')
        )

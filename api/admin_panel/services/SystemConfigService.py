# api/admin_panel/services/SystemConfigService.py
"""Service for getting/setting SystemConfig with cache and validation."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SystemConfigService:

    CACHE_TTL = 600  # 10 minutes

    @classmethod
    def get(cls, key: str, default=None):
        """Get a config value with cache."""
        cache_key = f'admin_panel:config:{key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from ..models.config import SystemConfig
            config = SystemConfig.objects.get(key=key)
            value = config.get_typed_value()
            cache.set(cache_key, value, cls.CACHE_TTL)
            return value
        except Exception:
            return default

    @classmethod
    def set(cls, key: str, value, value_type: str = 'string', user=None, group: str = 'general') -> bool:
        """Set a config value (create or update)."""
        try:
            from ..models.config import SystemConfig
            str_value = str(value) if not isinstance(value, str) else value
            obj, created = SystemConfig.objects.update_or_create(
                key=key,
                defaults={
                    'value': str_value,
                    'value_type': value_type,
                    'group': group,
                    'updated_by': user,
                }
            )
            cache.delete(f'admin_panel:config:{key}')
            cache.delete('admin_panel:config_all')
            return True
        except Exception as e:
            logger.error(f"SystemConfigService.set error for '{key}': {e}")
            return False

    @classmethod
    def get_all(cls, group: str = None) -> dict:
        """Get all config values as a dict, optionally filtered by group."""
        cached = cache.get('admin_panel:config_all')
        if cached and not group:
            return cached
        try:
            from ..models.config import SystemConfig
            qs = SystemConfig.objects.all()
            if group:
                qs = qs.filter(group=group)
            result = {c.key: c.get_typed_value() for c in qs}
            if not group:
                cache.set('admin_panel:config_all', result, cls.CACHE_TTL)
            return result
        except Exception as e:
            logger.error(f"SystemConfigService.get_all error: {e}")
            return {}

    @classmethod
    def get_public(cls) -> dict:
        """Get all public config values (for API exposure)."""
        try:
            from ..models.config import SystemConfig
            qs = SystemConfig.objects.filter(is_public=True)
            return {c.key: c.get_typed_value() for c in qs}
        except Exception:
            return {}

    @classmethod
    def clear_cache(cls, key: str = None):
        """Clear config cache for a key or all keys."""
        if key:
            cache.delete(f'admin_panel:config:{key}')
        else:
            try:
                from ..models.config import SystemConfig
                for c in SystemConfig.objects.values_list('key', flat=True):
                    cache.delete(f'admin_panel:config:{c}')
            except Exception:
                pass
            cache.delete('admin_panel:config_all')

    @classmethod
    def validate_value(cls, key: str, value) -> tuple:
        """Validate a value against its config's validation_regex. Returns (is_valid, error_msg)."""
        import re
        try:
            from ..models.config import SystemConfig
            config = SystemConfig.objects.get(key=key)
            if config.validation_regex:
                if not re.match(config.validation_regex, str(value)):
                    return False, f"Value does not match required pattern: {config.validation_regex}"
            return True, ''
        except SystemConfig.DoesNotExist:
            return True, ''
        except Exception as e:
            return False, str(e)
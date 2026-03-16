# api/cache/apps.py
"""
Cache App Configuration - Beautiful verbose names
"""
from django.apps import AppConfig


class CacheConfig(AppConfig):
    """Earnify Cache System - Redis & Memcached"""
    name = 'api.cache'
    verbose_name = '⚡ Cache System'
    verbose_name_plural = '⚡ Cache System'

    def ready(self):
        """Import signals when app is ready"""
        try:
            import api.cache.signals  # noqa: F401
        except ImportError:
            pass

"""
tenants/apps.py
Tenants app configuration for Django
"""
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tasks.tenants'
    verbose_name = 'Multi-Tenant Management'
    
    def ready(self):
        """Initialize tenant-related signals and utilities."""
        try:
            import tenants.signals  # noqa
        except ImportError:
            pass

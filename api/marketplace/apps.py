"""
marketplace/apps.py
"""
from django.apps import AppConfig
class MarketplaceConfig(AppConfig):
    name         = "api.marketplace"
    label        = "marketplace"
    verbose_name = "Marketplace"
    default_auto_field = "django.db.models.BigAutoField"
    def ready(self):
        try:
            import api.marketplace.signals
        except ImportError:
            pass
        try:
            import api.marketplace.WEBHOOKS.event_dispatcher
        except ImportError:
            pass
        try:
            from api.marketplace.admin import _force_register_marketplace
            _force_register_marketplace()
        except Exception as e:
            print(f"[WARN] Marketplace admin: {e}")

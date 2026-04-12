from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
class MonetizationToolsConfig(AppConfig):
    name = "api.monetization_tools"
    label = "monetization_tools"
    verbose_name = _("Monetization Tools")
    default_auto_field = "django.db.models.BigAutoField"
    def ready(self):
        try:
            from . import signals
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("signals import failed: %s", exc)
        try:
            from api.monetization_tools.admin import _force_register_monetization_tools
            _force_register_monetization_tools()
        except Exception as e:
            print(f"[WARN] Monetization Tools admin: {e}")

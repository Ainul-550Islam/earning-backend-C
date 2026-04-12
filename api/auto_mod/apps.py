# =============================================================================
# auto_mod/apps.py
# =============================================================================

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AutoModConfig(AppConfig):
    name               = "api.auto_mod"
    label              = "auto_mod"
    verbose_name       = _("AI Auto-Moderation")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        try:
            import api.auto_mod.receivers  # noqa: F401
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception(
                "auto_mod.ready: failed to import receivers: %s", exc
            )
    def ready(self):
        try:
            from api.auto_mod.admin import _force_register_auto_mod
            _force_register_auto_mod()
        except Exception as e:
            pass

# =============================================================================
# version_control/apps.py
# =============================================================================

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class VersionControlConfig(AppConfig):
    name               = "api.version_control"
    label              = "version_control"
    verbose_name       = _("Version Control & App Updates")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        try:
            import api.version_control.receivers  # noqa: F401
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception(
                "version_control.ready: failed to import receivers: %s", exc
            )
    def ready(self):
        try:
            from api.version_control.admin import _force_register_version_control
            _force_register_version_control()
        except Exception as e:
            pass

"""
Messaging AppConfig
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MessagingConfig(AppConfig):
    name = "api.messaging"
    label = "messaging"
    verbose_name = _("Messaging")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        try:
            from . import receivers  # noqa: F401
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "MessagingConfig.ready(): failed to import receivers: %s", exc
            )

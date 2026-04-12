"""
Messaging AppConfig — connects all receivers on startup.
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MessagingConfig(AppConfig):
    name = "api.messaging"
    label = "messaging"
    verbose_name = _("Messaging")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """
        Connect all signal receivers on startup.
        Called once when Django starts.
        """
        try:
            from . import receivers       # noqa: F401 — general messaging receivers
            from . import receivers_cpa   # noqa: F401 — CPA business event receivers
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "MessagingConfig.ready(): failed to connect receivers: %s", exc
            )

"""
Gamification AppConfig — Django app configuration.

Connects signal receivers in ready() so they are registered
exactly once when the app is fully loaded.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class GamificationConfig(AppConfig):
    name = "api.gamification"
    label = "gamification"
    verbose_name = _("Gamification")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """
        Import receivers here (not at module top-level) to avoid
        circular imports and ensure models are fully loaded first.
        """
        try:
            from . import receivers  # noqa: F401 — side-effect import
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "GamificationConfig.ready(): failed to import receivers: %s", exc
            )

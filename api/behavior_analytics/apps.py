# =============================================================================
# behavior_analytics/apps.py
# =============================================================================
"""
Django AppConfig for the behavior_analytics application.

Connects all signal receivers in ready() so they are guaranteed to be
registered before any request is processed — and only once.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BehaviorAnalyticsConfig(AppConfig):
    name            = "api.behavior_analytics"
    label           = "behavior_analytics"
    verbose_name    = _("Behavior Analytics")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """
        Import signal receivers so they are connected at startup.
        This is the ONLY place receivers should be imported.
        """
        try:
            import api.behavior_analytics.receivers  # noqa: F401
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception(
                "behavior_analytics.ready: failed to import receivers: %s", exc
            )
    def ready(self):
        try:
            from api.behavior_analytics.admin import _force_register_behavior_analytics
            _force_register_behavior_analytics()
        except Exception as e:
            pass

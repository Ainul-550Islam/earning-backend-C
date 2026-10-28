# engagement/apps.py  — FINAL with signal_receivers
from django.apps import AppConfig


class EngagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "api.engagement"
    label              = "engagement"
    verbose_name       = "Engagement & Gamification"

    def ready(self):
        """Connect all signal handlers when Django starts."""
        # Internal engagement signals
        try:
            import api.engagement.signals.handlers  # noqa: F401
        except Exception:
            pass

        # External 50-module signal receivers (safe — all wrapped in try/except)
        try:
            import api.engagement.services.adapters.signal_receivers  # noqa: F401
        except Exception as e:
            import logging
            logging.getLogger("engagement").warning(
                f"signal_receivers load failed (non-fatal): {e}"
            )

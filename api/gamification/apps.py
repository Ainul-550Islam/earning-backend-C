"""
Gamification AppConfig — Django app configuration.

Connects signal receivers in ready() so they are registered
exactly once when the app is fully loaded.
Enhanced with new models integration and comprehensive setup.
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
        Import receivers and setup components here (not at module top-level) to avoid
        circular imports and ensure models are fully loaded first.
        """
        import logging
        _log = logging.getLogger(__name__)

        _safe_imports = [
            ("receivers",           "signal receivers"),
            ("consumers",           "WebSocket consumers"),
            ("tasks",               "Celery tasks"),
            ("celery_beat_config",  "Celery beat config"),
            ("monitoring",          "monitoring"),
            ("analytics",           "analytics"),
            ("caching",             "caching"),
            ("encryption",          "encryption"),
            ("notifications_push",  "push notifications"),
            ("webhooks",            "webhooks"),
            ("feature_flags",       "feature flags"),
            ("compliance",          "compliance"),
            ("background_jobs",     "background jobs"),
            ("data_export",         "data export"),
            ("search",              "search"),
            ("plugins",             "plugins"),
            ("registry",            "registry"),
        ]

        for module_name, description in _safe_imports:
            try:
                __import__(f"api.gamification.{module_name}")
            except ImportError:
                pass  # optional dependency
            except Exception as exc:
                _log.warning(
                    "GamificationConfig.ready(): failed to import %s: %s",
                    description, exc
                )

        try:
            from api.gamification.admin import _force_register_gamification
            _force_register_gamification()
        except Exception as exc:
            _log.warning("GamificationConfig.ready(): admin registration failed: %s", exc)

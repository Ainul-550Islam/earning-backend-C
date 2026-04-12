# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
AppConfig for api.webhooks
"""

from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    """
    Ainul Enterprise Engine — Webhook Application Configuration.
    Manages lifecycle hooks, signal registration, and module init.
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.webhooks"
    verbose_name = "⚡ Webhook Dispatch Engine"

    def ready(self):
        import api.webhooks.signals  # noqa: F401 — register signal handlers
        try:
            from api.webhooks.admin import _force_register_webhooks
            _force_register_webhooks()
        except Exception as e:
            pass

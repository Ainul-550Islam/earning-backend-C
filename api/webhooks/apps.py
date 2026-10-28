# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
AppConfig for api.webhooks

FIX APPLIED:
  - ready() now imports BOTH signals.py (root handlers with @receiver)
    AND signals/ subdirectory handlers via signals/connector.py
  - Default aging policy is seeded at startup
  - Graceful degradation: errors in optional setup don't crash startup
"""

from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    """
    Ainul Enterprise Engine — Webhook Application Configuration.

    Startup sequence (ready):
      1. Register root signal handlers (signals.py)
      2. Connect subdirectory signal handlers (signals/connector.py)
      3. Register admin (if needed)
      4. Seed default aging policy
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.webhooks"
    verbose_name = "⚡ Webhook Dispatch Engine"

    def ready(self):
        # Custom exception available for misconfiguration: WebhookConfigurationError
        # 1. Root signal handlers (wallet, user, fraud, kyc — already @receiver decorated)
        import api.webhooks.signals  # noqa: F401

        # 2. Subdirectory signal handlers — previously floating, now connected
        try:
            import api.webhooks.signals.connector  # noqa: F401
        except Exception:
            pass  # connector is optional; degrades gracefully

        # 3. Admin force-register
        try:
            from api.webhooks.admin import _force_register_webhooks
            _force_register_webhooks()
        except Exception:
            pass

        # 4. Seed default aging policy (runs once, idempotent)
        try:
            from django.db import connection
            tables = connection.introspection.table_names()
            if "webhooks_webhookagingpolicy" in tables:
                from api.webhooks.models.aging import WebhookAgingPolicy
                WebhookAgingPolicy.objects.get_or_create(owner=None)
        except Exception:
            pass

# api/wallet/apps.py
"""
Wallet app configuration.
Registers all signals, receivers, plugins, and event handlers on startup.
"""
from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "api.wallet"
    label              = "wallet"
    verbose_name       = "Wallet — World #1 System"

    def ready(self):
        """
        Called once when Django starts.
        Register all signals, event handlers, receivers, plugins, registry.
        """
        # ── 1. Signals (core) ────────────────────────────────
        try:
            import api.wallet.signals  # noqa: F401
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"signals import: {e}")

        # ── 2. CPAlead signals ───────────────────────────────
        try:
            from api.wallet.signals_cap import connect_cpalead_signals
            connect_cpalead_signals()
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"signals_cap: {e}")

        # ── 3. Receivers (extra signal handlers) ─────────────
        try:
            from api.wallet.receivers import connect_receivers
            connect_receivers()
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"receivers: {e}")

        # ── 4. Event handlers (event bus subscriptions) ───────
        try:
            import api.wallet.event_handlers  # noqa: F401
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"event_handlers: {e}")

        # ── 5. Service registry ──────────────────────────────
        try:
            from api.wallet.registry import wallet_registry
            wallet_registry._auto_register()
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"registry: {e}")

        # ── 6. Built-in hooks ────────────────────────────────
        try:
            import api.wallet.hooks  # noqa: F401 — registers built-in hooks
        except Exception as e:
            import logging
            logging.getLogger("wallet.apps").warning(f"hooks: {e}")

        # ── 7. Plugin system ─────────────────────────────────
        # External apps register plugins in their own ready()
        # via: from api.wallet.plugins import plugin_registry
        # plugin_registry.register(MyPlugin())

        import logging
        logging.getLogger("wallet.apps").info(
            "WalletConfig.ready() — signals, events, receivers, registry, hooks all connected"
        )

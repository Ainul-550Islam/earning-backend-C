# api/admin_panel/apps.py
from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.admin_panel"
    verbose_name = "Admin Panel"

    def ready(self):
        import logging
        logger = logging.getLogger(__name__)

        # 1. Connect Django signals
        try:
            import api.admin_panel.signals  # noqa
        except ImportError:
            pass
        try:
            from api.admin_panel.signals import connect_all_signals
            connect_all_signals()
        except Exception as e:
            logger.warning(f"Signal connection deferred: {e}")

        # 2. Connect INTEGRATION_SYSTEM signals
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.integ_signals import integration_event  # noqa
            logger.debug("[AdminPanel] Integration signals connected")
        except Exception as e:
            logger.warning(f"Integration signals deferred: {e}")

        # 3. Auto-discover all app adapters in INTEGRATION_SYSTEM registry
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.integ_registry import registry
            discovered = registry.auto_discover()
            logger.info(f"[AdminPanel] Integration registry: {discovered} apps discovered")
        except Exception as e:
            logger.warning(f"Integration registry deferred: {e}")

        # 4. Register built-in adapters
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.integ_adapter import BUILTIN_ADAPTERS
            from api.admin_panel.INTEGRATION_SYSTEM.integ_registry import registry
            for app_name, adapter_class in BUILTIN_ADAPTERS.items():
                if not registry.is_registered(app_name):
                    registry.register(
                        app_name,
                        adapter_class=adapter_class,
                        capabilities=adapter_class.capabilities,
                        description=adapter_class.description,
                    )
        except Exception as e:
            logger.warning(f"Built-in adapter registration deferred: {e}")

        # 5. Register search handlers
        try:
            from api.admin_panel.search import register_default_handlers
            register_default_handlers()
            logger.debug("[AdminPanel] Search handlers registered")
        except Exception as e:
            logger.warning(f"Search handlers deferred: {e}")

        # 6. Setup KB signal routing
        try:
            from api.admin_panel.signals_kb import setup_kb_signal_routing
            setup_kb_signal_routing()
            logger.debug("[AdminPanel] KB signal routing setup")
        except Exception as e:
            logger.warning(f"KB signals deferred: {e}")

        # 7. Start EventBus built-in subscribers
        try:
            from api.admin_panel.INTEGRATION_SYSTEM import event_bus  # noqa — triggers subscriptions
        except Exception as e:
            logger.warning(f"EventBus init deferred: {e}")

        # 6. DB connection
        try:
            from django.db import connection
            connection.ensure_connection()
        except Exception:
            pass

        # Auto-fire on_ready for all registered extensions
        try:
            from api.admin_panel.plugins import extension_registry
            extension_registry.run_all_ready()
        except Exception as e:
            logger.warning(f"Extension on_ready: {e}")


def _post_migrate_sync(sender, **kwargs):
    if getattr(sender, "label", None) != "admin_panel":
        return  # post_migrate fires per app; once is enough
    try:
        from api.admin_panel.admin.legacy_admin import _sync_all_apps_to_modern_site
        _sync_all_apps_to_modern_site()
    except Exception as e:
        print(f"[WARN] admin sync failed: {e}")


from django.db.models.signals import post_migrate
post_migrate.connect(_post_migrate_sync)

# earning_backend/api/notifications/apps.py
"""
Notifications App Configuration.
This is the central initialization file for the entire notification system.
All signals, hooks, plugins, services and integration systems are wired here.
"""
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.notifications'
    label = 'notifications'
    verbose_name = '🔔 Notifications Management'

    def ready(self):
        """
        Initialize the entire notification system.
        Called once when Django starts.

        Order matters:
        1. Import core models (registers with Django ORM)
        2. Register admin
        3. Connect signals via signals_cap
        4. Wire hooks pipeline
        5. Register provider plugins
        6. Initialize integration system (EventBus, auto-discovery)
        7. Initialize workflow engine
        8. Patch notification service
        9. Pre-load Celery tasks
        """

        # ── 1. Register Django admin for all models ─────────────────────
        self._register_admin()

        # ── 2. Connect all signals (via signals_cap) ─────────────────────
        self._connect_signals()

        # ── 3. Wire hook pipeline built-in hooks ─────────────────────────
        self._init_hooks()

        # ── 4. Register provider plugins ──────────────────────────────────
        self._register_plugins()

        # ── 5. Initialize Integration System ──────────────────────────────
        self._init_integration_system()

        # ── 6. Initialize Workflow Engine ──────────────────────────────────
        self._init_workflow_engine()

        # ── 7. Patch NotificationService ──────────────────────────────────
        self._patch_notification_service()

        # ── 8. Pre-load Celery task modules ───────────────────────────────
        self._preload_tasks()

        # ── 9. Initialize Feature Flags ───────────────────────────────────
        self._init_feature_flags()

        print('[OK] Notifications System fully initialized ✅')

    # ------------------------------------------------------------------
    # Init helpers
    # ------------------------------------------------------------------

    def _register_admin(self):
        try:
            from django.contrib import admin
            from .models import (
                Notification, NotificationTemplate, NotificationPreference,
                DeviceToken, NotificationCampaign, NotificationAnalytics,
                NotificationRule, NotificationFeedback, NotificationLog, Notice,
            )
            for model in [Notification, NotificationTemplate, NotificationPreference,
                          DeviceToken, NotificationCampaign, NotificationAnalytics,
                          NotificationRule, NotificationFeedback, NotificationLog, Notice]:
                if not admin.site.is_registered(model):
                    try:
                        admin.site.register(model)
                    except Exception:
                        pass

            # Register 17 new split models
            try:
                from api.notifications.admin_new_models import register_all_new_models
                register_all_new_models()
            except Exception as e:
                print(f'[WARN] admin_new_models: {e}')

        except Exception as e:
            print(f'[WARN] admin registration: {e}')

    def _connect_signals(self):
        """Connect all receivers to signals using signals_cap."""
        try:
            from api.notifications.signals_cap import connect_all
            connect_all()
        except Exception as e:
            print(f'[WARN] signals_cap: {e}')

        # Also import legacy signals.py for backward compat
        try:
            import api.notifications.signals  # noqa: F401
        except Exception:
            pass

    def _init_hooks(self):
        """Hook pipeline is self-initializing via module-level decorators in hooks.py."""
        try:
            import api.notifications.hooks  # noqa: F401 — triggers decorator registration
        except Exception as e:
            print(f'[WARN] hooks: {e}')

    def _register_plugins(self):
        """Register all provider plugins in the plugin registry."""
        try:
            from api.notifications.plugins import register_builtin_providers
            register_builtin_providers()
        except Exception as e:
            print(f'[WARN] plugins: {e}')

    def _init_integration_system(self):
        """Initialize the 18-file integration system."""
        try:
            from api.notifications.integration_system.apps import init_integration_system
            init_integration_system()
        except Exception as e:
            print(f'[WARN] integration_system: {e}')

    def _init_workflow_engine(self):
        """Initialize workflow engine (built-in workflows are registered on import)."""
        try:
            import api.notifications.workflow  # noqa: F401 — triggers built-in workflow registration
            import api.notifications.funnel    # noqa: F401 — initializes funnel + RFM services
        except Exception as e:
            print(f'[WARN] workflow/funnel: {e}')

    def _patch_notification_service(self):
        """Apply patches to the monolithic NotificationService."""
        try:
            from api.notifications.services.NotificationService import patch_notification_service
            patch_notification_service()
        except Exception as e:
            print(f'[WARN] notification_service patch: {e}')

    def _preload_tasks(self):
        """Pre-load all Celery task modules for autodiscovery."""
        # Initialize liquid template engine
        try:
            import api.notifications.liquid_templates  # noqa
        except Exception: pass

        task_modules = [
            'api.notifications._tasks_core',
            'api.notifications._serializers_core',
            'api.notifications.tasks.send_push_tasks',
            'api.notifications.tasks.send_email_tasks',
            'api.notifications.tasks.send_sms_tasks',
            'api.notifications.tasks.campaign_tasks',
            'api.notifications.tasks.batch_send_tasks',
            'api.notifications.tasks.retry_tasks',
            'api.notifications.tasks.schedule_tasks',
            'api.notifications.tasks.delivery_tracking_tasks',
            'api.notifications.tasks.fatigue_check_tasks',
            'api.notifications.tasks.insight_tasks',
            'api.notifications.tasks.cleanup_tasks',
            'api.notifications.tasks.token_refresh_tasks',
            'api.notifications.tasks.unsubscribe_tasks',
            'api.notifications.tasks.ab_test_tasks',
            'api.notifications.tasks.journey_tasks',
            'api.notifications.tasks.background_tasks',
            'api.notifications.integration_system.tasks',
        ]
        for module in task_modules:
            try:
                __import__(module)
            except Exception:
                pass

    def _init_feature_flags(self):
        """Load feature flags from settings."""
        try:
            import api.notifications.feature_flags  # noqa: F401
        except Exception:
            pass

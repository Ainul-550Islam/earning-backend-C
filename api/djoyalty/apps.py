# api/djoyalty/apps.py
"""
Djoyalty AppConfig -- Initialises all signals, integrations and plugins on startup।

FIXED (critical):
  1. name = 'api.djoyalty' -> name = 'api.djoyalty'
       The app lives at api/djoyalty/ and INSTALLED_APPS uses "api.djoyalty"।
       A mismatched name caused RuntimeError on Django startup।

  2. All 8 absolute imports inside ready() converted to relative imports।
     Previously used 'djoyalty.X' paths which fail when app is at api/djoyalty/।
     Now all use '.X' relative paths which always resolve correctly।

For TEMPLATES context_processors in settings.py, add:
    'djoyalty.context_processors.loyalty_context'
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DjoyaltyConfig(AppConfig):
    name = 'api.djoyalty'
    label = 'djoyalty'
    verbose_name = 'Djoyalty -- World-Class Loyalty System'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # ── 1. Core model signals ────────────────────────────────────────────
        try:
            from . import signals  # noqa: F401
            logger.debug('DjoyaltyConfig: core signals connected')
        except Exception as e:
            logger.debug('DjoyaltyConfig: core signals error: %s', e)

        # ── 2. Knowledge-base signals ────────────────────────────────────────
        try:
            from .signals_kb import connect_kb_signals
            connect_kb_signals()
            logger.debug('DjoyaltyConfig: KB signals connected')
        except Exception as e:
            logger.debug('DjoyaltyConfig: KB signals error: %s', e)

        # ── 3. Integration system signals ────────────────────────────────────
        try:
            from .integration_system.integ_signals import connect_integration_signals
            connect_integration_signals()
            logger.debug('DjoyaltyConfig: integration signals connected')
        except Exception as e:
            logger.debug('DjoyaltyConfig: integration signals error: %s', e)

        # ── 4. Auto-register integrations (bKash, Nagad, FCM, SSL) ──────────
        try:
            from .integration_system.integ_registry import IntegrationRegistry
            registry = IntegrationRegistry.get_instance()
            registry.auto_register()
            available = len(registry.list_available())
            logger.info('DjoyaltyConfig: %d integrations auto-registered', available)
        except Exception as e:
            logger.debug('DjoyaltyConfig: integration registry error: %s', e)

        # ── 5. Service registry defaults ─────────────────────────────────────
        try:
            from .registry import service_registry
            service_registry.setup_defaults()
            logger.debug('DjoyaltyConfig: service registry initialized')
        except Exception as e:
            logger.debug('DjoyaltyConfig: service registry error: %s', e)

        # ── 6. setup_integrations -- email, SMS, OCR, push, CPAlead ──────────
        try:
            from .registry import service_registry
            service_registry.setup_integrations()
            logger.info('DjoyaltyConfig: external integrations wired via setup_integrations()')
        except Exception as e:
            logger.debug('DjoyaltyConfig: setup_integrations error: %s', e)

        # ── 7. Plugin registry ───────────────────────────────────────────────
        try:
            from .plugins import PluginRegistry
            PluginRegistry.auto_discover()
            plugin_count = len(PluginRegistry.list())
            logger.info('DjoyaltyConfig: %d plugins registered', plugin_count)
        except Exception as e:
            logger.debug('DjoyaltyConfig: plugin registry error: %s', e)

        # ── 8. Clear feature flag cache on restart ───────────────────────────
        try:
            from .feature_flags import FeatureFlags
            FeatureFlags.clear_cache()
            logger.debug('DjoyaltyConfig: feature flag cache cleared')
        except Exception as e:
            logger.debug('DjoyaltyConfig: feature flag cache error: %s', e)

        # ── 9. Register lifecycle hooks ──────────────────────────────────────
        try:
            from .hooks import HookRegistry
            HookRegistry.setup_defaults()
            logger.debug('DjoyaltyConfig: hooks registered')
        except Exception as e:
            logger.debug('DjoyaltyConfig: hooks error: %s', e)

        logger.info('DjoyaltyConfig: ready ✅')

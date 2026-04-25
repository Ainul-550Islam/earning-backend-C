# api/notifications/integration_system/apps.py
"""
Integration System initialization.
Called from notifications/apps.py ready() via init_integration_system().
"""
import logging
logger = logging.getLogger(__name__)


def init_integration_system():
    """Initialize the integration system. Called from notifications/apps.py."""

    # 1. Wire Django signals → EventBus (pre-defined signals)
    try:
        from .integ_signals import wire_django_signals
        wire_django_signals()
        logger.info('[IntegSystem] Django signals wired')
    except Exception as e:
        logger.warning(f'[IntegSystem] signals: {e}')

    # 2. Wire notification subscriptions on EventBus
    try:
        from .event_bus import _wire_notification_subscriptions
        _wire_notification_subscriptions()
        logger.info('[IntegSystem] EventBus subscriptions wired')
    except Exception as e:
        logger.warning(f'[IntegSystem] event_bus: {e}')

    # 3. Register built-in adapters
    try:
        from .integ_registry import registry
        from .integ_adapter import NotificationIntegrationAdapter, WalletIntegrationAdapter
        registry.register('notifications', NotificationIntegrationAdapter,
                          description='Notifications adapter', overwrite=True)
        registry.register('wallet', WalletIntegrationAdapter,
                          description='Wallet adapter', overwrite=True)
        logger.info('[IntegSystem] Built-in adapters registered')
    except Exception as e:
        logger.warning(f'[IntegSystem] registry: {e}')

    # 4. AUTO-DISCOVER all installed apps (MAIN NEW FEATURE)
    # Scans every INSTALLED_APP for integ_config.py and wires automatically
    try:
        from .auto_discovery import auto_discovery
        results = auto_discovery.discover_all()
        discovered = [k for k, v in results.items() if v]
        logger.info(
            f'[IntegSystem] Auto-discovery complete: '
            f'{len(discovered)} modules wired automatically'
        )
        if discovered:
            # Only log modules that actually had integ_config.py
            registered = auto_discovery.get_registered_modules()
            if registered:
                logger.info(f'[IntegSystem] Auto-registered: {registered}')
    except Exception as e:
        logger.warning(f'[IntegSystem] auto_discovery: {e}')

    logger.info('[IntegSystem] ✅ Integration System fully initialized')

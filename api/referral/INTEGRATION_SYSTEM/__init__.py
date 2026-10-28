# api/referral/INTEGRATION_SYSTEM/__init__.py
# Integration System — 18 files connecting referral with the entire project
#
# Usage from any module:
#   from api.referral.INTEGRATION_SYSTEM import get_bridge, get_event_bus
#   bridge = get_bridge()
#   bridge.on_task_earned(user=user, task=task, amount=100)
# ============================================================

from .bridge import get_bridge, ReferralBridge
from .event_bus import get_event_bus, ReferralEventBus
from .integ_registry import get_registry, IntegrationRegistry
from .integ_constants import (
    EVENT_TASK_COMPLETED, EVENT_OFFER_COMPLETED,
    EVENT_USER_REGISTERED, EVENT_FRAUD_CONFIRMED,
    EVENT_WITHDRAWAL_APPROVED, QUEUE_REFERRAL_HIGH,
    QUEUE_REFERRAL_NORMAL, QUEUE_REFERRAL_LOW,
)
from .integ_exceptions import (
    IntegrationError, ModuleUnavailableError, AdapterError,
    HandlerError, BridgeError, ValidationError,
    SyncConflictError, CircuitBreakerOpenError, AuthBridgeError,
)
from .integ_adapter import AdapterFactory, WalletAdapter, NotificationAdapter
from .data_bridge import DataBridge
from .data_validator import IntegrationValidator
from .fallback_logic import get_breaker, with_retry, with_fallback
from .auth_bridge import ReferralAuthBridge
from .performance_monitor import get_monitor, track_commission_processing, track_fraud_check
from .integ_audit_logs import ReferralAuditLogger
from .health_check import ReferralHealthCheck, health_check_view
from .sync_manager import ReferralSyncManager
from .message_queue import ReferralMessageQueue
from .webhooks_integration import get_webhook_urlpatterns


def initialize(app_config=None) -> None:
    """
    Initialize the entire integration system.
    Called from api/referral/apps.py → ready()
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 1. Discover available modules
        registry = get_registry()
        registry.auto_discover_modules()

        # 2. Register default event handlers
        from .integ_registry import setup_default_handlers
        setup_default_handlers(registry)

        # 3. Setup event bus
        from .event_bus import setup_event_bus
        bus = get_event_bus()
        setup_event_bus(bus)

        logger.info(
            f'[INTEGRATION_SYSTEM] Initialized — '
            f'modules={registry.get_available_modules()}'
        )
    except Exception as e:
        logger.error(f'[INTEGRATION_SYSTEM] Init error: {e}')


__all__ = [
    # Bridge (main entry point)
    'get_bridge', 'ReferralBridge',

    # Event Bus
    'get_event_bus', 'ReferralEventBus',

    # Registry
    'get_registry', 'IntegrationRegistry',

    # Constants
    'EVENT_TASK_COMPLETED', 'EVENT_OFFER_COMPLETED',
    'EVENT_USER_REGISTERED', 'EVENT_FRAUD_CONFIRMED',
    'EVENT_WITHDRAWAL_APPROVED',
    'QUEUE_REFERRAL_HIGH', 'QUEUE_REFERRAL_NORMAL', 'QUEUE_REFERRAL_LOW',

    # Exceptions
    'IntegrationError', 'ModuleUnavailableError', 'AdapterError',
    'HandlerError', 'BridgeError', 'ValidationError',
    'SyncConflictError', 'CircuitBreakerOpenError', 'AuthBridgeError',

    # Adapters
    'AdapterFactory', 'WalletAdapter', 'NotificationAdapter',

    # Data
    'DataBridge', 'IntegrationValidator',

    # Fallback
    'get_breaker', 'with_retry', 'with_fallback',

    # Auth
    'ReferralAuthBridge',

    # Monitoring
    'get_monitor', 'track_commission_processing', 'track_fraud_check',
    'ReferralAuditLogger',

    # Health
    'ReferralHealthCheck', 'health_check_view',

    # Sync
    'ReferralSyncManager',

    # Queue
    'ReferralMessageQueue',

    # Webhooks
    'get_webhook_urlpatterns',

    # Init
    'initialize',
]
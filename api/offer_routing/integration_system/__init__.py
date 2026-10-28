"""
Integration System Package for Offer Routing System

Exposes all integration classes and singletons for use
across the application and via the API layer.
"""

from .auth_bridge import AuthBridge, PermissionManager, TokenStore, SessionStore
from .bridge import IntegrationBridge
from .data_bridge import DataBridge
from .data_validator import DataValidator
from .event_bus import EventBus
from .fallback_logic import FallbackLogic
from .health_check import HealthCheck
from .integ_adapter import (
    BaseIntegrationAdapter, WebhookIntegrationAdapter,
    APIIntegrationAdapter, create_adapter
)
from .integ_audit_logs import IntegrationAuditLogger
from .integ_handler import IntegrationHandler
from .integ_registry import IntegrationRegistry
from .message_queue import MessageQueueIntegration
from .performance_monitor import PerformanceMonitor
from .webhooks_integration import WebhookIntegration
from .integ_constants import (
    IntegrationType, IntegrationStatus, IntegrationPriority,
    IntegrationEvent, DEFAULT_INTEGRATION_TIMEOUT, DEFAULT_RETRY_ATTEMPTS,
    INTEGRATION_ERROR_CODES, INTEGRATION_PERFORMANCE_THRESHOLDS
)
from .integ_exceptions import (
    IntegrationError, IntegrationConfigurationError,
    IntegrationConnectionError, IntegrationTimeoutError,
    IntegrationAuthenticationError, IntegrationAuthorizationError,
    IntegrationValidationError, IntegrationDataError,
    IntegrationSyncError, IntegrationRateLimitError,
    IntegrationNotFoundError, IntegrationDisabledError
)

# Module-level singletons — instantiated once at import
auth_bridge = AuthBridge()
integration_bridge = IntegrationBridge()
data_bridge = DataBridge()
data_validator = DataValidator()
event_bus = EventBus()
fallback_logic = FallbackLogic()
health_check_service = HealthCheck()
audit_logger = IntegrationAuditLogger()
integration_handler = IntegrationHandler()
integration_registry = IntegrationRegistry()
performance_monitor = PerformanceMonitor()

__all__ = [
    # Core classes
    'AuthBridge', 'PermissionManager', 'TokenStore', 'SessionStore',
    'IntegrationBridge',
    'DataBridge',
    'DataValidator',
    'EventBus',
    'FallbackLogic',
    'HealthCheck',
    'BaseIntegrationAdapter', 'WebhookIntegrationAdapter',
    'APIIntegrationAdapter', 'create_adapter',
    'IntegrationAuditLogger',
    'IntegrationHandler',
    'IntegrationRegistry',
    'MessageQueueIntegration',
    'PerformanceMonitor',
    'WebhookIntegration',
    # Singletons
    'auth_bridge',
    'integration_bridge',
    'data_bridge',
    'data_validator',
    'event_bus',
    'fallback_logic',
    'health_check_service',
    'audit_logger',
    'integration_handler',
    'integration_registry',
    'performance_monitor',
    # Enums / Constants
    'IntegrationType', 'IntegrationStatus', 'IntegrationPriority',
    'IntegrationEvent', 'DEFAULT_INTEGRATION_TIMEOUT', 'DEFAULT_RETRY_ATTEMPTS',
    'INTEGRATION_ERROR_CODES', 'INTEGRATION_PERFORMANCE_THRESHOLDS',
    # Exceptions
    'IntegrationError', 'IntegrationConfigurationError',
    'IntegrationConnectionError', 'IntegrationTimeoutError',
    'IntegrationAuthenticationError', 'IntegrationAuthorizationError',
    'IntegrationValidationError', 'IntegrationDataError',
    'IntegrationSyncError', 'IntegrationRateLimitError',
    'IntegrationNotFoundError', 'IntegrationDisabledError',
]

from .integ_cache import IntegrationCache, integ_cache

# Signal utilities
from .integ_signals import (
    send_integration_signal,
    create_signal_context,
    validate_signal_data,
    enrich_signal_data,
    create_error_context,
    create_performance_context,
)

# Add to __all__
__all__ += ['IntegrationCache', 'integ_cache',

    'send_integration_signal', 'create_signal_context',
    'validate_signal_data', 'enrich_signal_data',
    'create_error_context', 'create_performance_context',
]

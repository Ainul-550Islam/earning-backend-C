# api/rate_limit/integ_exceptions.py
"""
Integration exceptions for rate limit module.

Provides custom exception classes for integration system.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration errors."""
    
    def __init__(self, message: str, error_code: str = None, 
                 integration_id: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'INTEGRATION_ERROR'
        self.integration_id = integration_id
        self.details = details or {}
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'integration_id': self.integration_id,
            'details': self.details,
            'timestamp': self.timestamp
        }


class IntegrationTimeoutError(IntegrationError):
    """Exception raised when integration operation times out."""
    
    def __init__(self, message: str, timeout: int = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_TIMEOUT', **kwargs)
        self.timeout = timeout


class IntegrationConnectionError(IntegrationError):
    """Exception raised when integration connection fails."""
    
    def __init__(self, message: str, connection_details: Dict[str, Any] = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_CONNECTION_ERROR', **kwargs)
        self.connection_details = connection_details or {}


class IntegrationAuthenticationError(IntegrationError):
    """Exception raised when integration authentication fails."""
    
    def __init__(self, message: str, auth_type: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_AUTH_ERROR', **kwargs)
        self.auth_type = auth_type


class IntegrationAuthorizationError(IntegrationError):
    """Exception raised when integration authorization fails."""
    
    def __init__(self, message: str, required_permissions: List[str] = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_AUTHZ_ERROR', **kwargs)
        self.required_permissions = required_permissions or []


class IntegrationRateLimitError(IntegrationError):
    """Exception raised when integration rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = None, limit_details: Dict[str, Any] = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_RATE_LIMIT', **kwargs)
        self.retry_after = retry_after
        self.limit_details = limit_details or {}


class IntegrationValidationError(IntegrationError):
    """Exception raised when integration data validation fails."""
    
    def __init__(self, message: str, validation_errors: List[str] = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_VALIDATION_ERROR', **kwargs)
        self.validation_errors = validation_errors or []


class IntegrationConfigurationError(IntegrationError):
    """Exception raised when integration configuration is invalid."""
    
    def __init__(self, message: str, config_field: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_CONFIG_ERROR', **kwargs)
        self.config_field = config_field


class IntegrationNotFoundError(IntegrationError):
    """Exception raised when integration is not found."""
    
    def __init__(self, message: str, integration_type: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_NOT_FOUND', **kwargs)
        self.integration_type = integration_type


class IntegrationDisabledError(IntegrationError):
    """Exception raised when integration is disabled."""
    
    def __init__(self, message: str, disabled_reason: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_DISABLED', **kwargs)
        self.disabled_reason = disabled_reason


class IntegrationAdapterError(IntegrationError):
    """Exception raised when integration adapter fails."""
    
    def __init__(self, message: str, adapter_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_ADAPTER_ERROR', **kwargs)
        self.adapter_name = adapter_name


class IntegrationTransformError(IntegrationError):
    """Exception raised when data transformation fails."""
    
    def __init__(self, message: str, transformer_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_TRANSFORM_ERROR', **kwargs)
        self.transformer_name = transformer_name


class IntegrationBridgeError(IntegrationError):
    """Exception raised when integration bridge fails."""
    
    def __init__(self, message: str, bridge_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_BRIDGE_ERROR', **kwargs)
        self.bridge_name = bridge_name


class IntegrationCircuitBreakerError(IntegrationError):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, message: str, circuit_breaker_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_CIRCUIT_BREAKER', **kwargs)
        self.circuit_breaker_name = circuit_breaker_name


class IntegrationEventBusError(IntegrationError):
    """Exception raised when event bus operation fails."""
    
    def __init__(self, message: str, event_type: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_EVENT_BUS_ERROR', **kwargs)
        self.event_type = event_type


class IntegrationWebhookError(IntegrationError):
    """Exception raised when webhook delivery fails."""
    
    def __init__(self, message: str, webhook_url: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_WEBHOOK_ERROR', **kwargs)
        self.webhook_url = webhook_url


class IntegrationMessageQueueError(IntegrationError):
    """Exception raised when message queue operation fails."""
    
    def __init__(self, message: str, queue_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_MESSAGE_QUEUE_ERROR', **kwargs)
        self.queue_name = queue_name


class IntegrationDataBridgeError(IntegrationError):
    """Exception raised when data bridge operation fails."""
    
    def __init__(self, message: str, bridge_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_DATA_BRIDGE_ERROR', **kwargs)
        self.bridge_name = bridge_name


class IntegrationVersionError(IntegrationError):
    """Exception raised when version compatibility issue occurs."""
    
    def __init__(self, message: str, current_version: str = None, required_version: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_VERSION_ERROR', **kwargs)
        self.current_version = current_version
        self.required_version = required_version


class IntegrationSecurityError(IntegrationError):
    """Exception raised when security issue occurs."""
    
    def __init__(self, message: str, security_issue: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_SECURITY_ERROR', **kwargs)
        self.security_issue = security_issue


class IntegrationComplianceError(IntegrationError):
    """Exception raised when compliance issue occurs."""
    
    def __init__(self, message: str, compliance_rule: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_COMPLIANCE_ERROR', **kwargs)
        self.compliance_rule = compliance_rule


class IntegrationRegistryError(IntegrationError):
    """Exception raised when registry operation fails."""
    
    def __init__(self, message: str, registry_operation: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_REGISTRY_ERROR', **kwargs)
        self.registry_operation = registry_operation


class IntegrationHandlerError(IntegrationError):
    """Exception raised when event handler fails."""
    
    def __init__(self, message: str, handler_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_HANDLER_ERROR', **kwargs)
        self.handler_name = handler_name


class IntegrationSignalError(IntegrationError):
    """Exception raised when signal operation fails."""
    
    def __init__(self, message: str, signal_name: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_SIGNAL_ERROR', **kwargs)
        self.signal_name = signal_name


class IntegrationFallbackError(IntegrationError):
    """Exception raised when fallback mechanism fails."""
    
    def __init__(self, message: str, fallback_type: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_FALLBACK_ERROR', **kwargs)
        self.fallback_type = fallback_type


class IntegrationAuthBridgeError(IntegrationError):
    """Exception raised when authentication bridge fails."""
    
    def __init__(self, message: str, auth_system: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_AUTH_BRIDGE_ERROR', **kwargs)
        self.auth_system = auth_system


class IntegrationPerformanceError(IntegrationError):
    """Exception raised when performance threshold is exceeded."""
    
    def __init__(self, message: str, metric_name: str = None, threshold: float = None, actual_value: float = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_PERFORMANCE_ERROR', **kwargs)
        self.metric_name = metric_name
        self.threshold = threshold
        self.actual_value = actual_value


class IntegrationRetryExhaustedError(IntegrationError):
    """Exception raised when retry attempts are exhausted."""
    
    def __init__(self, message: str, max_attempts: int = None, attempts_made: int = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_RETRY_EXHAUSTED', **kwargs)
        self.max_attempts = max_attempts
        self.attempts_made = attempts_made


class IntegrationDataCorruptionError(IntegrationError):
    """Exception raised when data corruption is detected."""
    
    def __init__(self, message: str, corrupted_field: str = None, expected_value: str = None, actual_value: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_DATA_CORRUPTION', **kwargs)
        self.corrupted_field = corrupted_field
        self.expected_value = expected_value
        self.actual_value = actual_value


class IntegrationResourceExhaustedError(IntegrationError):
    """Exception raised when integration resources are exhausted."""
    
    def __init__(self, message: str, resource_type: str = None, usage: int = None, limit: int = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_RESOURCE_EXHAUSTED', **kwargs)
        self.resource_type = resource_type
        self.usage = usage
        self.limit = limit


class IntegrationDependencyError(IntegrationError):
    """Exception raised when integration dependency is missing or fails."""
    
    def __init__(self, message: str, dependency_name: str = None, dependency_version: str = None, **kwargs):
        super().__init__(message, error_code='INTEGRATION_DEPENDENCY_ERROR', **kwargs)
        self.dependency_name = dependency_name
        self.dependency_version = dependency_version


# Exception utility functions
def is_integration_error(exception: Exception) -> bool:
    """Check if exception is an integration error."""
    return isinstance(exception, IntegrationError)


def get_integration_error_code(exception: Exception) -> str:
    """Get error code from integration exception."""
    if isinstance(exception, IntegrationError):
        return exception.error_code
    return 'UNKNOWN_ERROR'


def get_integration_error_details(exception: Exception) -> Dict[str, Any]:
    """Get detailed error information."""
    if isinstance(exception, IntegrationError):
        return exception.to_dict()
    else:
        return {
            'error_type': type(exception).__name__,
            'message': str(exception),
            'error_code': 'UNKNOWN_ERROR'
        }


def log_integration_error(exception: Exception, context: Dict[str, Any] = None):
    """Log integration error with context."""
    error_details = get_integration_error_details(exception)
    
    log_data = {
        'error_details': error_details,
        'context': context or {}
    }
    
    if isinstance(exception, IntegrationTimeoutError):
        logger.error(f"Integration timeout: {error_details['message']}", extra=log_data)
    elif isinstance(exception, IntegrationConnectionError):
        logger.error(f"Integration connection error: {error_details['message']}", extra=log_data)
    elif isinstance(exception, IntegrationAuthenticationError):
        logger.error(f"Integration authentication error: {error_details['message']}", extra=log_data)
    elif isinstance(exception, IntegrationRateLimitError):
        logger.warning(f"Integration rate limit: {error_details['message']}", extra=log_data)
    else:
        logger.error(f"Integration error: {error_details['message']}", extra=log_data)


def create_integration_error(error_type: str, message: str, **kwargs) -> IntegrationError:
    """
    Create an integration error instance by type.
    
    Args:
        error_type: Type of error
        message: Error message
        **kwargs: Additional error parameters
        
    Returns:
        Integration error instance
    """
    error_classes = {
        'timeout': IntegrationTimeoutError,
        'connection': IntegrationConnectionError,
        'authentication': IntegrationAuthenticationError,
        'authorization': IntegrationAuthorizationError,
        'rate_limit': IntegrationRateLimitError,
        'validation': IntegrationValidationError,
        'configuration': IntegrationConfigurationError,
        'not_found': IntegrationNotFoundError,
        'disabled': IntegrationDisabledError,
        'adapter': IntegrationAdapterError,
        'transform': IntegrationTransformError,
        'bridge': IntegrationBridgeError,
        'circuit_breaker': IntegrationCircuitBreakerError,
        'event_bus': IntegrationEventBusError,
        'webhook': IntegrationWebhookError,
        'message_queue': IntegrationMessageQueueError,
        'data_bridge': IntegrationDataBridgeError,
        'version': IntegrationVersionError,
        'security': IntegrationSecurityError,
        'compliance': IntegrationComplianceError,
        'registry': IntegrationRegistryError,
        'handler': IntegrationHandlerError,
        'signal': IntegrationSignalError,
        'fallback': IntegrationFallbackError,
        'auth_bridge': IntegrationAuthBridgeError,
        'performance': IntegrationPerformanceError,
        'retry_exhausted': IntegrationRetryExhaustedError,
        'data_corruption': IntegrationDataCorruptionError,
        'resource_exhausted': IntegrationResourceExhaustedError,
        'dependency': IntegrationDependencyError
    }
    
    error_class = error_classes.get(error_type, IntegrationError)
    return error_class(message, **kwargs)


# Exception handler decorator
def handle_integration_errors(default_return=None, log_error=True):
    """
    Decorator to handle integration errors gracefully.
    
    Args:
        default_return: Default return value on error
        log_error: Whether to log errors
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrationError as e:
                if log_error:
                    log_integration_error(e, {'function': func.__name__, 'args': args, 'kwargs': kwargs})
                
                if default_return is not None:
                    return default_return
                
                raise
            except Exception as e:
                if log_error:
                    logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                
                if default_return is not None:
                    return default_return
                
                raise
        return wrapper
    return decorator


# Export all exceptions and utilities
__all__ = [
    'IntegrationError',
    'IntegrationTimeoutError',
    'IntegrationConnectionError',
    'IntegrationAuthenticationError',
    'IntegrationAuthorizationError',
    'IntegrationRateLimitError',
    'IntegrationValidationError',
    'IntegrationConfigurationError',
    'IntegrationNotFoundError',
    'IntegrationDisabledError',
    'IntegrationAdapterError',
    'IntegrationTransformError',
    'IntegrationBridgeError',
    'IntegrationCircuitBreakerError',
    'IntegrationEventBusError',
    'IntegrationWebhookError',
    'IntegrationMessageQueueError',
    'IntegrationDataBridgeError',
    'IntegrationVersionError',
    'IntegrationSecurityError',
    'IntegrationComplianceError',
    'IntegrationRegistryError',
    'IntegrationHandlerError',
    'IntegrationSignalError',
    'IntegrationFallbackError',
    'IntegrationAuthBridgeError',
    'IntegrationPerformanceError',
    'IntegrationRetryExhaustedError',
    'IntegrationDataCorruptionError',
    'IntegrationResourceExhaustedError',
    'IntegrationDependencyError',
    'is_integration_error',
    'get_integration_error_code',
    'get_integration_error_details',
    'log_integration_error',
    'create_integration_error',
    'handle_integration_errors'
]

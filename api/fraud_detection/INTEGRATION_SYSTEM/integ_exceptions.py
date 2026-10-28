# =============================================================================
# INTEGRATION_SYSTEM/integ_exceptions.py
# =============================================================================
"""
Integration System Custom Exceptions.

Provides comprehensive exception hierarchy for integration operations
with specific error handling and user-friendly messages.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone as tz

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """
    Base exception class for integration errors.
    
    All integration-specific exceptions should inherit from this class
    to provide consistent error handling and logging.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 integration_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.integration_name = integration_name
        self.details = details or {}
        self.timestamp = datetime.now(tz.utc)
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'integration_name': self.integration_name,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class IntegrationConnectionError(IntegrationError):
    """
    Exception raised when integration connection fails.
    
    This exception is raised when the system cannot establish
    or maintain a connection to an external integration.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 retry_after: Optional[int] = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, error_code='INT_CONNECTION_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationTimeoutError(IntegrationError):
    """
    Exception raised when integration operation times out.
    
    This exception is raised when an integration operation
    exceeds the configured timeout period.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 timeout_duration: Optional[float] = None, **kwargs):
        self.timeout_duration = timeout_duration
        super().__init__(message, error_code='INT_TIMEOUT_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationAuthenticationError(IntegrationError):
    """
    Exception raised when integration authentication fails.
    
    This exception is raised when authentication credentials
    are invalid, expired, or missing.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 auth_type: Optional[str] = None, **kwargs):
        self.auth_type = auth_type
        super().__init__(message, error_code='INT_AUTH_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationValidationError(IntegrationError):
    """
    Exception raised when integration data validation fails.
    
    This exception is raised when request/response data
    fails validation checks.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 field_name: Optional[str] = None, validation_rule: Optional[str] = None, **kwargs):
        self.field_name = field_name
        self.validation_rule = validation_rule
        super().__init__(message, error_code='INT_VALIDATION_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationRateLimitError(IntegrationError):
    """
    Exception raised when integration rate limit is exceeded.
    
    This exception is raised when the external system
    rejects requests due to rate limiting.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 retry_after: Optional[int] = None, rate_limit: Optional[int] = None, **kwargs):
        self.retry_after = retry_after
        self.rate_limit = rate_limit
        super().__init__(message, error_code='INT_RATE_LIMIT_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationConfigurationError(IntegrationError):
    """
    Exception raised when integration configuration is invalid.
    
    This exception is raised when integration settings
    are missing, invalid, or incompatible.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 config_key: Optional[str] = None, config_value: Optional[Any] = None, **kwargs):
        self.config_key = config_key
        self.config_value = config_value
        super().__init__(message, error_code='INT_CONFIG_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationNotFoundError(IntegrationError):
    """
    Exception raised when requested integration is not found.
    
    This exception is raised when trying to access
    an integration that doesn't exist or is not registered.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='INT_NOT_FOUND_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationDisabledError(IntegrationError):
    """
    Exception raised when integration is disabled.
    
    This exception is raised when trying to use
    an integration that has been explicitly disabled.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='INT_DISABLED_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationQuotaExceededError(IntegrationError):
    """
    Exception raised when integration quota is exceeded.
    
    This exception is raised when the integration
    exceeds its allocated quota or limits.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 quota_type: Optional[str] = None, quota_limit: Optional[int] = None, **kwargs):
        self.quota_type = quota_type
        self.quota_limit = quota_limit
        super().__init__(message, error_code='INT_QUOTA_EXCEEDED_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationVersionError(IntegrationError):
    """
    Exception raised when integration version is incompatible.
    
    This exception is raised when there are version
    compatibility issues between systems.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 current_version: Optional[str] = None, required_version: Optional[str] = None, **kwargs):
        self.current_version = current_version
        self.required_version = required_version
        super().__init__(message, error_code='INT_VERSION_ERROR', 
                        integration_name=integration_name, **kwargs)


class IntegrationPermissionError(IntegrationError):
    """
    Exception raised when integration permission is denied.
    
    This exception is raised when the integration
    lacks required permissions for an operation.
    """
    
    def __init__(self, message: str, integration_name: Optional[str] = None,
                 required_permission: Optional[str] = None, **kwargs):
        self.required_permission = required_permission
        super().__init__(message, error_code='INT_PERMISSION_ERROR', 
                        integration_name=integration_name, **kwargs)


# Bridge System Exceptions
class BridgeError(IntegrationError):
    """Base exception for bridge system errors."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        self.bridge_name = bridge_name
        super().__init__(message, error_code='BRIDGE_ERROR', **kwargs)


class BridgeConnectionError(BridgeError):
    """Exception for bridge connection failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='BRIDGE_CONNECTION_ERROR', 
                        bridge_name=bridge_name, **kwargs)


class BridgeTimeoutError(BridgeError):
    """Exception for bridge timeout failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='BRIDGE_TIMEOUT_ERROR', 
                        bridge_name=bridge_name, **kwargs)


class BridgeValidationError(BridgeError):
    """Exception for bridge validation failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='BRIDGE_VALIDATION_ERROR', 
                        bridge_name=bridge_name, **kwargs)


# Event Bus Exceptions
class EventBusError(IntegrationError):
    """Base exception for event bus errors."""
    
    def __init__(self, message: str, event_id: Optional[str] = None, **kwargs):
        self.event_id = event_id
        super().__init__(message, error_code='EVENT_BUS_ERROR', **kwargs)


class EventBusSubscriptionError(EventBusError):
    """Exception for event bus subscription failures."""
    
    def __init__(self, message: str, event_pattern: Optional[str] = None, **kwargs):
        self.event_pattern = event_pattern
        super().__init__(message, error_code='EVENT_BUS_SUBSCRIPTION_ERROR', **kwargs)


class EventBusDeliveryError(EventBusError):
    """Exception for event bus delivery failures."""
    
    def __init__(self, message: str, event_id: Optional[str] = None, 
                 subscription_id: Optional[str] = None, **kwargs):
        self.subscription_id = subscription_id
        super().__init__(message, error_code='EVENT_BUS_DELIVERY_ERROR', **kwargs)


# Circuit Breaker Exceptions
class CircuitBreakerError(IntegrationError):
    """Base exception for circuit breaker errors."""
    
    def __init__(self, message: str, circuit_breaker_name: Optional[str] = None, **kwargs):
        self.circuit_breaker_name = circuit_breaker_name
        super().__init__(message, error_code='CIRCUIT_BREAKER_ERROR', **kwargs)


class CircuitBreakerOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, message: str, circuit_breaker_name: Optional[str] = None, 
                 recovery_timeout: Optional[int] = None, **kwargs):
        self.recovery_timeout = recovery_timeout
        super().__init__(message, error_code='CIRCUIT_BREAKER_OPEN_ERROR', 
                        circuit_breaker_name=circuit_breaker_name, **kwargs)


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Exception for circuit breaker timeout failures."""
    
    def __init__(self, message: str, circuit_breaker_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='CIRCUIT_BREAKER_TIMEOUT_ERROR', 
                        circuit_breaker_name=circuit_breaker_name, **kwargs)


# Transformation Exceptions
class TransformationError(IntegrationError):
    """Base exception for data transformation errors."""
    
    def __init__(self, message: str, source_format: Optional[str] = None, 
                 target_format: Optional[str] = None, **kwargs):
        self.source_format = source_format
        self.target_format = target_format
        super().__init__(message, error_code='TRANSFORMATION_ERROR', **kwargs)


class TransformationValidationError(TransformationError):
    """Exception for transformation validation failures."""
    
    def __init__(self, message: str, validation_rule: Optional[str] = None, **kwargs):
        self.validation_rule = validation_rule
        super().__init__(message, error_code='TRANSFORMATION_VALIDATION_ERROR', **kwargs)


class TransformationFormatError(TransformationError):
    """Exception for unsupported format transformations."""
    
    def __init__(self, message: str, source_format: Optional[str] = None, 
                 target_format: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='TRANSFORMATION_FORMAT_ERROR', 
                        source_format=source_format, target_format=target_format, **kwargs)


# Versioning Exceptions
class VersionError(IntegrationError):
    """Base exception for versioning errors."""
    
    def __init__(self, message: str, version: Optional[str] = None, **kwargs):
        self.version = version
        super().__init__(message, error_code='VERSION_ERROR', **kwargs)


class VersionCompatibilityError(VersionError):
    """Exception for version compatibility issues."""
    
    def __init__(self, message: str, version1: Optional[str] = None, 
                 version2: Optional[str] = None, **kwargs):
        self.version1 = version1
        self.version2 = version2
        super().__init__(message, error_code='VERSION_COMPATIBILITY_ERROR', **kwargs)


class VersionMigrationError(VersionError):
    """Exception for version migration failures."""
    
    def __init__(self, message: str, from_version: Optional[str] = None, 
                 to_version: Optional[str] = None, **kwargs):
        self.from_version = from_version
        self.to_version = to_version
        super().__init__(message, error_code='VERSION_MIGRATION_ERROR', **kwargs)


# Webhook Exceptions
class WebhookError(IntegrationError):
    """Base exception for webhook errors."""
    
    def __init__(self, message: str, webhook_url: Optional[str] = None, **kwargs):
        self.webhook_url = webhook_url
        super().__init__(message, error_code='WEBHOOK_ERROR', **kwargs)


class WebhookDeliveryError(WebhookError):
    """Exception for webhook delivery failures."""
    
    def __init__(self, message: str, webhook_url: Optional[str] = None, 
                 event_type: Optional[str] = None, **kwargs):
        self.event_type = event_type
        super().__init__(message, error_code='WEBHOOK_DELIVERY_ERROR', 
                        webhook_url=webhook_url, **kwargs)


class WebhookValidationError(WebhookError):
    """Exception for webhook validation failures."""
    
    def __init__(self, message: str, webhook_url: Optional[str] = None, 
                 validation_error: Optional[str] = None, **kwargs):
        self.validation_error = validation_error
        super().__init__(message, error_code='WEBHOOK_VALIDATION_ERROR', 
                        webhook_url=webhook_url, **kwargs)


# Message Queue Exceptions
class MessageQueueError(IntegrationError):
    """Base exception for message queue errors."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None, **kwargs):
        self.queue_name = queue_name
        super().__init__(message, error_code='MESSAGE_QUEUE_ERROR', **kwargs)


class MessageQueueConnectionError(MessageQueueError):
    """Exception for message queue connection failures."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='MESSAGE_QUEUE_CONNECTION_ERROR', 
                        queue_name=queue_name, **kwargs)


class MessageQueuePublishError(MessageQueueError):
    """Exception for message queue publish failures."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None, 
                 message_id: Optional[str] = None, **kwargs):
        self.message_id = message_id
        super().__init__(message, error_code='MESSAGE_QUEUE_PUBLISH_ERROR', 
                        queue_name=queue_name, **kwargs)


class MessageQueueConsumeError(MessageQueueError):
    """Exception for message queue consume failures."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='MESSAGE_QUEUE_CONSUME_ERROR', 
                        queue_name=queue_name, **kwargs)


# Data Bridge Exceptions
class DataBridgeError(IntegrationError):
    """Base exception for data bridge errors."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        self.bridge_name = bridge_name
        super().__init__(message, error_code='DATA_BRIDGE_ERROR', **kwargs)


class DataBridgeConnectionError(DataBridgeError):
    """Exception for data bridge connection failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='DATA_BRIDGE_CONNECTION_ERROR', 
                        bridge_name=bridge_name, **kwargs)


class DataBridgeTransformationError(DataBridgeError):
    """Exception for data bridge transformation failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        super().__init__(message, error_code='DATA_BRIDGE_TRANSFORMATION_ERROR', 
                        bridge_name=bridge_name, **kwargs)


# Data Validator Exceptions
class DataValidatorError(IntegrationError):
    """Base exception for data validator errors."""
    
    def __init__(self, message: str, validator_name: Optional[str] = None, **kwargs):
        self.validator_name = validator_name
        super().__init__(message, error_code='DATA_VALIDATOR_ERROR', **kwargs)


class DataValidationError(DataValidatorError):
    """Exception for data validation failures."""
    
    def __init__(self, message: str, field_name: Optional[str] = None, 
                 validation_rule: Optional[str] = None, **kwargs):
        self.field_name = field_name
        self.validation_rule = validation_rule
        super().__init__(message, error_code='DATA_VALIDATION_ERROR', **kwargs)


# Auth Bridge Exceptions
class AuthBridgeError(IntegrationError):
    """Base exception for auth bridge errors."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, **kwargs):
        self.bridge_name = bridge_name
        super().__init__(message, error_code='AUTH_BRIDGE_ERROR', **kwargs)


class AuthBridgePermissionError(AuthBridgeError):
    """Exception for auth bridge permission failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, 
                 required_permission: Optional[str] = None, **kwargs):
        self.required_permission = required_permission
        super().__init__(message, error_code='AUTH_BRIDGE_PERMISSION_ERROR', 
                        bridge_name=bridge_name, **kwargs)


class AuthBridgeTokenError(AuthBridgeError):
    """Exception for auth bridge token failures."""
    
    def __init__(self, message: str, bridge_name: Optional[str] = None, 
                 token_type: Optional[str] = None, **kwargs):
        self.token_type = token_type
        super().__init__(message, error_code='AUTH_BRIDGE_TOKEN_ERROR', 
                        bridge_name=bridge_name, **kwargs)


# Performance Monitor Exceptions
class PerformanceMonitorError(IntegrationError):
    """Base exception for performance monitor errors."""
    
    def __init__(self, message: str, monitor_name: Optional[str] = None, **kwargs):
        self.monitor_name = monitor_name
        super().__init__(message, error_code='PERFORMANCE_MONITOR_ERROR', **kwargs)


class PerformanceMetricError(PerformanceMonitorError):
    """Exception for performance metric errors."""
    
    def __init__(self, message: str, metric_name: Optional[str] = None, **kwargs):
        self.metric_name = metric_name
        super().__init__(message, error_code='PERFORMANCE_METRIC_ERROR', **kwargs)


# Audit Log Exceptions
class AuditLogError(IntegrationError):
    """Base exception for audit log errors."""
    
    def __init__(self, message: str, log_id: Optional[str] = None, **kwargs):
        self.log_id = log_id
        super().__init__(message, error_code='AUDIT_LOG_ERROR', **kwargs)


class AuditLogStorageError(AuditLogError):
    """Exception for audit log storage failures."""
    
    def __init__(self, message: str, storage_type: Optional[str] = None, **kwargs):
        self.storage_type = storage_type
        super().__init__(message, error_code='AUDIT_LOG_STORAGE_ERROR', **kwargs)


# Health Check Exceptions
class HealthCheckError(IntegrationError):
    """Base exception for health check errors."""
    
    def __init__(self, message: str, check_name: Optional[str] = None, **kwargs):
        self.check_name = check_name
        super().__init__(message, error_code='HEALTH_CHECK_ERROR', **kwargs)


class HealthCheckTimeoutError(HealthCheckError):
    """Exception for health check timeout failures."""
    
    def __init__(self, message: str, check_name: Optional[str] = None, 
                 timeout_duration: Optional[float] = None, **kwargs):
        self.timeout_duration = timeout_duration
        super().__init__(message, error_code='HEALTH_CHECK_TIMEOUT_ERROR', 
                        check_name=check_name, **kwargs)


# Sync Manager Exceptions
class SyncManagerError(IntegrationError):
    """Base exception for sync manager errors."""
    
    def __init__(self, message: str, sync_id: Optional[str] = None, **kwargs):
        self.sync_id = sync_id
        super().__init__(message, error_code='SYNC_MANAGER_ERROR', **kwargs)


class SyncConflictError(SyncManagerError):
    """Exception for sync conflict errors."""
    
    def __init__(self, message: str, conflict_type: Optional[str] = None, **kwargs):
        self.conflict_type = conflict_type
        super().__init__(message, error_code='SYNC_CONFLICT_ERROR', **kwargs)


class SyncTimeoutError(SyncManagerError):
    """Exception for sync timeout failures."""
    
    def __init__(self, message: str, sync_id: Optional[str] = None, 
                 timeout_duration: Optional[float] = None, **kwargs):
        self.timeout_duration = timeout_duration
        super().__init__(message, error_code='SYNC_TIMEOUT_ERROR', **kwargs)


# Fallback Logic Exceptions
class FallbackError(IntegrationError):
    """Base exception for fallback logic errors."""
    
    def __init__(self, message: str, fallback_name: Optional[str] = None, **kwargs):
        self.fallback_name = fallback_name
        super().__init__(message, error_code='FALLBACK_ERROR', **kwargs)


class FallbackExecutionError(FallbackError):
    """Exception for fallback execution failures."""
    
    def __init__(self, message: str, fallback_name: Optional[str] = None, 
                 original_error: Optional[Exception] = None, **kwargs):
        self.original_error = original_error
        super().__init__(message, error_code='FALLBACK_EXECUTION_ERROR', 
                        fallback_name=fallback_name, **kwargs)


class FallbackNotAvailableError(FallbackError):
    """Exception when no fallback is available."""
    
    def __init__(self, message: str, operation_name: Optional[str] = None, **kwargs):
        self.operation_name = operation_name
        super().__init__(message, error_code='FALLBACK_NOT_AVAILABLE_ERROR', **kwargs)


# Exception handler utilities
def handle_integration_exception(exception: Exception) -> Dict[str, Any]:
    """
    Handle integration exceptions and return standardized response.
    
    Args:
        exception: The exception to handle
        
    Returns:
        Standardized error response dictionary
    """
    if isinstance(exception, IntegrationError):
        return exception.to_dict()
    else:
        return {
            'error': 'InternalServerError',
            'message': 'An unexpected error occurred',
            'error_code': 'INTERNAL_ERROR',
            'timestamp': datetime.now(tz.utc).isoformat()
        }


def log_integration_exception(exception: Exception, logger_instance: logging.Logger, 
                            context: str = "") -> None:
    """
    Log integration exceptions with appropriate level.
    
    Args:
        exception: The exception to log
        logger_instance: Logger instance
        context: Additional context information
    """
    if isinstance(exception, IntegrationError):
        error_context = f" in {context}" if context else ""
        
        if exception.error_code in ['INT_CONNECTION_ERROR', 'INT_AUTH_ERROR', 'INT_TIMEOUT_ERROR']:
            logger_instance.error(f"Integration error{error_context}: {exception.message}")
        elif exception.error_code in ['INT_RATE_LIMIT_ERROR', 'INT_VALIDATION_ERROR']:
            logger_instance.warning(f"Integration warning{error_context}: {exception.message}")
        else:
            logger_instance.info(f"Integration info{error_context}: {exception.message}")
    else:
        logger_instance.error(f"Unexpected error in {context}: {str(exception)}")


def get_exception_severity(exception: Exception) -> str:
    """
    Get severity level for exception.
    
    Args:
        exception: The exception to evaluate
        
    Returns:
        Severity level (low, medium, high, critical)
    """
    if isinstance(exception, IntegrationError):
        critical_errors = [
            'INT_CONNECTION_ERROR', 'INT_AUTH_ERROR', 'INT_TIMEOUT_ERROR',
            'CIRCUIT_BREAKER_OPEN_ERROR', 'SYNC_CONFLICT_ERROR'
        ]
        
        if exception.error_code in critical_errors:
            return 'critical'
        elif 'ERROR' in exception.error_code:
            return 'high'
        elif 'VALIDATION' in exception.error_code:
            return 'medium'
        else:
            return 'low'
    else:
        return 'critical'


def should_retry_exception(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.
    
    Args:
        exception: The exception to evaluate
        
    Returns:
        True if retry should be attempted
    """
    if isinstance(exception, IntegrationError):
        retryable_errors = [
            'INT_TIMEOUT_ERROR', 'INT_RATE_LIMIT_ERROR', 'INT_CONNECTION_ERROR'
        ]
        return exception.error_code in retryable_errors
    else:
        return False


def get_retry_delay(exception: Exception, attempt: int) -> int:
    """
    Get retry delay for exception.
    
    Args:
        exception: The exception that occurred
        attempt: Current attempt number
        
    Returns:
        Retry delay in seconds
    """
    if isinstance(exception, IntegrationRateLimitError):
        return exception.retry_after or (2 ** attempt)
    elif isinstance(exception, IntegrationTimeoutError):
        return min(2 ** attempt, 30)  # Max 30 seconds
    else:
        return 2 ** attempt  # Exponential backoff

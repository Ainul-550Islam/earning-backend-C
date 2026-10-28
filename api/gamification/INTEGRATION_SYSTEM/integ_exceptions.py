"""
Integration Exceptions — Custom exceptions for integration system.

This module provides comprehensive exception classes for the integration
system with proper error codes, messages, and handling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from .integ_constants import ErrorCode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Exception Classes
# ---------------------------------------------------------------------------

class IntegrationError(Exception):
    """Base exception for all integration system errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()
        
        logger.error(
            f"IntegrationError: {message} | Code: {error_code.value} | Details: {details}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None
        }


class ValidationError(IntegrationError):
    """Exception raised for data validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(
            message,
            ErrorCode.DATA_VALIDATION_ERROR,
            details,
            kwargs.get("cause")
        )
        self.field = field
        self.value = value


class ConfigurationError(IntegrationError):
    """Exception raised for configuration errors."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if config_key:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)
        
        super().__init__(
            message,
            ErrorCode.INVALID_REQUEST,
            details,
            kwargs.get("cause")
        )
        self.config_key = config_key
        self.config_value = config_value


# ---------------------------------------------------------------------------
# Connection and Network Exceptions
# ---------------------------------------------------------------------------

class ConnectionError(IntegrationError):
    """Exception raised for connection-related errors."""
    
    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if endpoint:
            details["endpoint"] = endpoint
        if timeout:
            details["timeout"] = timeout
        
        super().__init__(
            message,
            ErrorCode.CONNECTION_ERROR,
            details,
            kwargs.get("cause")
        )
        self.endpoint = endpoint
        self.timeout = timeout


class TimeoutError(IntegrationError):
    """Exception raised for timeout errors."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        timeout_duration: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if operation:
            details["operation"] = operation
        if timeout_duration:
            details["timeout_duration"] = timeout_duration
        
        super().__init__(
            message,
            ErrorCode.TIMEOUT_ERROR,
            details,
            kwargs.get("cause")
        )
        self.operation = operation
        self.timeout_duration = timeout_duration


class AuthenticationError(IntegrationError):
    """Exception raised for authentication errors."""
    
    def __init__(
        self,
        message: str,
        auth_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if auth_type:
            details["auth_type"] = auth_type
        
        super().__init__(
            message,
            ErrorCode.AUTHENTICATION_ERROR,
            details,
            kwargs.get("cause")
        )
        self.auth_type = auth_type


class AuthorizationError(IntegrationError):
    """Exception raised for authorization errors."""
    
    def __init__(
        self,
        message: str,
        required_permission: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if required_permission:
            details["required_permission"] = required_permission
        if user_id:
            details["user_id"] = user_id
        
        super().__init__(
            message,
            ErrorCode.AUTHORIZATION_ERROR,
            details,
            kwargs.get("cause")
        )
        self.required_permission = required_permission
        self.user_id = user_id


# ---------------------------------------------------------------------------
# Data and Format Exceptions
# ---------------------------------------------------------------------------

class DataFormatError(IntegrationError):
    """Exception raised for data format errors."""
    
    def __init__(
        self,
        message: str,
        expected_format: Optional[str] = None,
        actual_format: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if expected_format:
            details["expected_format"] = expected_format
        if actual_format:
            details["actual_format"] = actual_format
        
        super().__init__(
            message,
            ErrorCode.DATA_FORMAT_ERROR,
            details,
            kwargs.get("cause")
        )
        self.expected_format = expected_format
        self.actual_format = actual_format


class DataSizeError(IntegrationError):
    """Exception raised for data size errors."""
    
    def __init__(
        self,
        message: str,
        actual_size: Optional[int] = None,
        max_size: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if actual_size is not None:
            details["actual_size"] = actual_size
        if max_size is not None:
            details["max_size"] = max_size
        
        super().__init__(
            message,
            ErrorCode.DATA_SIZE_ERROR,
            details,
            kwargs.get("cause")
        )
        self.actual_size = actual_size
        self.max_size = max_size


class DataCorruptionError(IntegrationError):
    """Exception raised for data corruption errors."""
    
    def __init__(
        self,
        message: str,
        checksum_expected: Optional[str] = None,
        checksum_actual: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if checksum_expected:
            details["checksum_expected"] = checksum_expected
        if checksum_actual:
            details["checksum_actual"] = checksum_actual
        
        super().__init__(
            message,
            ErrorCode.DATA_CORRUPTION_ERROR,
            details,
            kwargs.get("cause")
        )
        self.checksum_expected = checksum_expected
        self.checksum_actual = checksum_actual


# ---------------------------------------------------------------------------
# System and Resource Exceptions
# ---------------------------------------------------------------------------

class SystemOverloadError(IntegrationError):
    """Exception raised when system is overloaded."""
    
    def __init__(
        self,
        message: str,
        current_load: Optional[float] = None,
        max_capacity: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if current_load is not None:
            details["current_load"] = current_load
        if max_capacity is not None:
            details["max_capacity"] = max_capacity
        
        super().__init__(
            message,
            ErrorCode.SYSTEM_OVERLOAD,
            details,
            kwargs.get("cause")
        )
        self.current_load = current_load
        self.max_capacity = max_capacity


class ResourceExhaustedError(IntegrationError):
    """Exception raised when resources are exhausted."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_usage: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if resource_type:
            details["resource_type"] = resource_type
        if resource_usage is not None:
            details["resource_usage"] = resource_usage
        
        super().__init__(
            message,
            ErrorCode.RESOURCE_EXHAUSTED,
            details,
            kwargs.get("cause")
        )
        self.resource_type = resource_type
        self.resource_usage = resource_usage


class ServiceUnavailableError(IntegrationError):
    """Exception raised when service is unavailable."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if service_name:
            details["service_name"] = service_name
        if retry_after:
            details["retry_after"] = retry_after
        
        super().__init__(
            message,
            ErrorCode.SERVICE_UNAVAILABLE,
            details,
            kwargs.get("cause")
        )
        self.service_name = service_name
        self.retry_after = retry_after


class RateLimitExceededError(IntegrationError):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str,
        current_rate: Optional[float] = None,
        limit: Optional[float] = None,
        reset_time: Optional[datetime] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if current_rate is not None:
            details["current_rate"] = current_rate
        if limit is not None:
            details["limit"] = limit
        if reset_time:
            details["reset_time"] = reset_time.isoformat()
        
        super().__init__(
            message,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            details,
            kwargs.get("cause")
        )
        self.current_rate = current_rate
        self.limit = limit
        self.reset_time = reset_time


# ---------------------------------------------------------------------------
# Integration-Specific Exceptions
# ---------------------------------------------------------------------------

class IntegrationNotFoundError(IntegrationError):
    """Exception raised when integration is not found."""
    
    def __init__(
        self,
        message: str,
        integration_id: Optional[str] = None,
        integration_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if integration_id:
            details["integration_id"] = integration_id
        if integration_type:
            details["integration_type"] = integration_type
        
        super().__init__(
            message,
            ErrorCode.INTEGRATION_NOT_FOUND,
            details,
            kwargs.get("cause")
        )
        self.integration_id = integration_id
        self.integration_type = integration_type


class IntegrationDisabledError(IntegrationError):
    """Exception raised when integration is disabled."""
    
    def __init__(
        self,
        message: str,
        integration_id: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if integration_id:
            details["integration_id"] = integration_id
        if reason:
            details["reason"] = reason
        
        super().__init__(
            message,
            ErrorCode.INTEGRATION_DISABLED,
            details,
            kwargs.get("cause")
        )
        self.integration_id = integration_id
        self.reason = reason


class IntegrationFailedError(IntegrationError):
    """Exception raised when integration operation fails."""
    
    def __init__(
        self,
        message: str,
        integration_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if integration_id:
            details["integration_id"] = integration_id
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message,
            ErrorCode.INTEGRATION_FAILED,
            details,
            kwargs.get("cause")
        )
        self.integration_id = integration_id
        self.operation = operation


# ---------------------------------------------------------------------------
# Circuit Breaker Exceptions
# ---------------------------------------------------------------------------

class CircuitBreakerError(IntegrationError):
    """Base exception for circuit breaker errors."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is open."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        failure_count: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if service_name:
            details["service_name"] = service_name
        if failure_count is not None:
            details["failure_count"] = failure_count
        
        super().__init__(
            message,
            ErrorCode.CIRCUIT_BREAKER_OPEN,
            details,
            kwargs.get("cause")
        )
        self.service_name = service_name
        self.failure_count = failure_count


class CircuitBreakerHalfOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is half-open."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if service_name:
            details["service_name"] = service_name
        
        super().__init__(
            message,
            ErrorCode.CIRCUIT_BREAKER_HALF_OPEN,
            details,
            kwargs.get("cause")
        )
        self.service_name = service_name


# ---------------------------------------------------------------------------
# Queue Exceptions
# ---------------------------------------------------------------------------

class QueueError(IntegrationError):
    """Base exception for queue errors."""
    pass


class QueueFullError(QueueError):
    """Exception raised when queue is full."""
    
    def __init__(
        self,
        message: str,
        queue_name: Optional[str] = None,
        current_size: Optional[int] = None,
        max_size: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if queue_name:
            details["queue_name"] = queue_name
        if current_size is not None:
            details["current_size"] = current_size
        if max_size is not None:
            details["max_size"] = max_size
        
        super().__init__(
            message,
            ErrorCode.QUEUE_FULL,
            details,
            kwargs.get("cause")
        )
        self.queue_name = queue_name
        self.current_size = current_size
        self.max_size = max_size


class QueueEmptyError(QueueError):
    """Exception raised when queue is empty."""
    
    def __init__(
        self,
        message: str,
        queue_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if queue_name:
            details["queue_name"] = queue_name
        
        super().__init__(
            message,
            ErrorCode.QUEUE_EMPTY,
            details,
            kwargs.get("cause")
        )
        self.queue_name = queue_name


class QueueTimeoutError(QueueError):
    """Exception raised for queue timeout errors."""
    
    def __init__(
        self,
        message: str,
        queue_name: Optional[str] = None,
        operation: Optional[str] = None,
        timeout_duration: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if queue_name:
            details["queue_name"] = queue_name
        if operation:
            details["operation"] = operation
        if timeout_duration:
            details["timeout_duration"] = timeout_duration
        
        super().__init__(
            message,
            ErrorCode.QUEUE_TIMEOUT,
            details,
            kwargs.get("cause")
        )
        self.queue_name = queue_name
        self.operation = operation
        self.timeout_duration = timeout_duration


# ---------------------------------------------------------------------------
# Version Exceptions
# ---------------------------------------------------------------------------

class VersionError(IntegrationError):
    """Base exception for version errors."""
    pass


class VersionMismatchError(VersionError):
    """Exception raised for version mismatch."""
    
    def __init__(
        self,
        message: str,
        expected_version: Optional[str] = None,
        actual_version: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if expected_version:
            details["expected_version"] = expected_version
        if actual_version:
            details["actual_version"] = actual_version
        
        super().__init__(
            message,
            ErrorCode.VERSION_MISMATCH,
            details,
            kwargs.get("cause")
        )
        self.expected_version = expected_version
        self.actual_version = actual_version


class VersionNotSupportedError(VersionError):
    """Exception raised when version is not supported."""
    
    def __init__(
        self,
        message: str,
        version: Optional[str] = None,
        supported_versions: Optional[List[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if version:
            details["version"] = version
        if supported_versions:
            details["supported_versions"] = supported_versions
        
        super().__init__(
            message,
            ErrorCode.VERSION_NOT_SUPPORTED,
            details,
            kwargs.get("cause")
        )
        self.version = version
        self.supported_versions = supported_versions


# ---------------------------------------------------------------------------
# Sync Exceptions
# ---------------------------------------------------------------------------

class SyncError(IntegrationError):
    """Base exception for synchronization errors."""
    pass


class SyncConflictError(SyncError):
    """Exception raised for synchronization conflicts."""
    
    def __init__(
        self,
        message: str,
        resource_id: Optional[str] = None,
        conflict_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if resource_id:
            details["resource_id"] = resource_id
        if conflict_type:
            details["conflict_type"] = conflict_type
        
        super().__init__(
            message,
            ErrorCode.SYNC_CONFLICT,
            details,
            kwargs.get("cause")
        )
        self.resource_id = resource_id
        self.conflict_type = conflict_type


class SyncTimeoutError(SyncError):
    """Exception raised for synchronization timeout."""
    
    def __init__(
        self,
        message: str,
        sync_operation: Optional[str] = None,
        timeout_duration: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if sync_operation:
            details["sync_operation"] = sync_operation
        if timeout_duration:
            details["timeout_duration"] = timeout_duration
        
        super().__init__(
            message,
            ErrorCode.SYNC_TIMEOUT,
            details,
            kwargs.get("cause")
        )
        self.sync_operation = sync_operation
        self.timeout_duration = timeout_duration


class SyncFailedError(SyncError):
    """Exception raised when synchronization fails."""
    
    def __init__(
        self,
        message: str,
        sync_operation: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if sync_operation:
            details["sync_operation"] = sync_operation
        if error_details:
            details["error_details"] = error_details
        
        super().__init__(
            message,
            ErrorCode.SYNC_FAILED,
            details,
            kwargs.get("cause")
        )
        self.sync_operation = sync_operation
        self.error_details = error_details


# ---------------------------------------------------------------------------
# Exception Utilities
# ---------------------------------------------------------------------------

def create_error_response(
    exception: IntegrationError,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """Create standardized error response from exception."""
    response = exception.to_dict()
    
    if include_traceback and exception.cause:
        import traceback
        response["traceback"] = traceback.format_exc()
    
    return response


def log_exception(
    exception: IntegrationError,
    additional_context: Optional[Dict[str, Any]] = None
) -> None:
    """Log exception with additional context."""
    context = additional_context or {}
    
    logger.error(
        f"Integration Exception: {exception.message} | "
        f"Code: {exception.error_code.value} | "
        f"Type: {exception.__class__.__name__} | "
        f"Context: {context} | "
        f"Details: {exception.details}"
    )


def is_retryable_error(exception: IntegrationError) -> bool:
    """Check if an exception is retryable."""
    retryable_codes = {
        ErrorCode.TIMEOUT_ERROR,
        ErrorCode.CONNECTION_ERROR,
        ErrorCode.SERVICE_UNAVAILABLE,
        ErrorCode.SYSTEM_OVERLOAD,
        ErrorCode.RATE_LIMIT_EXCEEDED,
        ErrorCode.QUEUE_FULL,
        ErrorCode.CIRCUIT_BREAKER_HALF_OPEN
    }
    
    return exception.error_code in retryable_codes


def get_retry_delay(
    exception: IntegrationError,
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0
) -> float:
    """Calculate retry delay for an exception."""
    if not is_retryable_error(exception):
        return 0.0
    
    delay = base_delay * (backoff_multiplier ** (attempt - 1))
    return min(delay, max_delay)


# Initialize logging
logger.info("Integration exceptions module initialized")

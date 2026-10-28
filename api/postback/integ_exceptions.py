"""
integ_exceptions.py – Integration exceptions for postback module.

Provides comprehensive exception handling including:
- Integration-specific exceptions
- Error codes and messages
- Exception hierarchy
- Error handling utilities
"""
from datetime import timedelta
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from django.utils import timezone

logger = logging.getLogger(__name__)


class IntegrationErrorCode(Enum):
    """Integration error code enumeration."""
    SUCCESS = "SUCCESS"
    GENERAL_ERROR = "GENERAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
    TRANSFORMATION_ERROR = "TRANSFORMATION_ERROR"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    DECRYPTION_ERROR = "DECRYPTION_ERROR"
    VERSION_MISMATCH_ERROR = "VERSION_MISMATCH_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    QUOTA_EXCEEDED_ERROR = "QUOTA_EXCEEDED_ERROR"
    SERVICE_UNAVAILABLE_ERROR = "SERVICE_UNAVAILABLE_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    CIRCUIT_BREAKER_ERROR = "CIRCUIT_BREAKER_ERROR"
    WEBHOOK_ERROR = "WEBHOOK_ERROR"
    QUEUE_ERROR = "QUEUE_ERROR"
    BRIDGE_ERROR = "BRIDGE_ERROR"
    EVENT_BUS_ERROR = "EVENT_BUS_ERROR"
    VALIDATOR_ERROR = "VALIDATOR_ERROR"
    SECURITY_ERROR = "SECURITY_ERROR"
    CACHE_ERROR = "CACHE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    FILE_SYSTEM_ERROR = "FILE_SYSTEM_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class IntegrationSeverity(Enum):
    """Integration severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntegrationException(Exception):
    """
    Base integration exception.
    
    Provides common functionality for all integration exceptions.
    """
    
    def __init__(self, message: str, error_code: IntegrationErrorCode = IntegrationErrorCode.GENERAL_ERROR,
                 severity: IntegrationSeverity = IntegrationSeverity.MEDIUM,
                 details: Dict[str, Any] = None, cause: Exception = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.timestamp = timezone.now()
        self.traceback_id = self._generate_traceback_id()
    
    def _generate_traceback_id(self) -> str:
        """Generate unique traceback ID."""
        import uuid
        return f"trace_{uuid.uuid4().hex[:12]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            'message': self.message,
            'error_code': self.error_code.value,
            'severity': self.severity.value,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'traceback_id': self.traceback_id,
            'cause': str(self.cause) if self.cause else None,
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"


class IntegrationTimeoutException(IntegrationException):
    """Integration timeout exception."""
    
    def __init__(self, message: str = "Integration request timed out", timeout: float = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.TIMEOUT_ERROR, **kwargs)
        self.timeout = timeout
        if timeout:
            self.details['timeout'] = timeout


class IntegrationConnectionException(IntegrationException):
    """Integration connection exception."""
    
    def __init__(self, message: str = "Failed to establish connection", **kwargs):
        super().__init__(message, IntegrationErrorCode.CONNECTION_ERROR, **kwargs)


class IntegrationAuthenticationException(IntegrationException):
    """Integration authentication exception."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, IntegrationErrorCode.AUTHENTICATION_ERROR, **kwargs)


class IntegrationAuthorizationException(IntegrationException):
    """Integration authorization exception."""
    
    def __init__(self, message: str = "Authorization failed", **kwargs):
        super().__init__(message, IntegrationErrorCode.AUTHORIZATION_ERROR, **kwargs)


class IntegrationValidationException(IntegrationException):
    """Integration validation exception."""
    
    def __init__(self, message: str = "Validation failed", validation_errors: List[str] = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.VALIDATION_ERROR, **kwargs)
        self.validation_errors = validation_errors or []
        if validation_errors:
            self.details['validation_errors'] = validation_errors


class IntegrationConfigurationException(IntegrationException):
    """Integration configuration exception."""
    
    def __init__(self, message: str = "Configuration error", config_key: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.CONFIGURATION_ERROR, **kwargs)
        self.config_key = config_key
        if config_key:
            self.details['config_key'] = config_key


class IntegrationProtocolException(IntegrationException):
    """Integration protocol exception."""
    
    def __init__(self, message: str = "Protocol error", protocol: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.PROTOCOL_ERROR, **kwargs)
        self.protocol = protocol
        if protocol:
            self.details['protocol'] = protocol


class IntegrationDataFormatException(IntegrationException):
    """Integration data format exception."""
    
    def __init__(self, message: str = "Data format error", format_type: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.DATA_FORMAT_ERROR, **kwargs)
        self.format_type = format_type
        if format_type:
            self.details['format_type'] = format_type


class IntegrationTransformationException(IntegrationException):
    """Integration transformation exception."""
    
    def __init__(self, message: str = "Data transformation failed", transformation_type: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.TRANSFORMATION_ERROR, **kwargs)
        self.transformation_type = transformation_type
        if transformation_type:
            self.details['transformation_type'] = transformation_type


class IntegrationVersionMismatchException(IntegrationException):
    """Integration version mismatch exception."""
    
    def __init__(self, message: str = "Version mismatch", expected_version: str = None, actual_version: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.VERSION_MISMATCH_ERROR, **kwargs)
        self.expected_version = expected_version
        self.actual_version = actual_version
        if expected_version:
            self.details['expected_version'] = expected_version
        if actual_version:
            self.details['actual_version'] = actual_version


class IntegrationRateLimitException(IntegrationException):
    """Integration rate limit exception."""
    
    def __init__(self, message: str = "Rate limit exceeded", limit: int = None, reset_time: datetime = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.RATE_LIMIT_ERROR, **kwargs)
        self.limit = limit
        self.reset_time = reset_time
        if limit:
            self.details['limit'] = limit
        if reset_time:
            self.details['reset_time'] = reset_time.isoformat()


class IntegrationQuotaExceededException(IntegrationException):
    """Integration quota exceeded exception."""
    
    def __init__(self, message: str = "Quota exceeded", quota_type: str = None, quota_limit: int = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.QUOTA_EXCEEDED_ERROR, **kwargs)
        self.quota_type = quota_type
        self.quota_limit = quota_limit
        if quota_type:
            self.details['quota_type'] = quota_type
        if quota_limit:
            self.details['quota_limit'] = quota_limit


class IntegrationServiceUnavailableException(IntegrationException):
    """Integration service unavailable exception."""
    
    def __init__(self, message: str = "Service unavailable", service_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.SERVICE_UNAVAILABLE_ERROR, **kwargs)
        self.service_name = service_name
        if service_name:
            self.details['service_name'] = service_name


class IntegrationDependencyException(IntegrationException):
    """Integration dependency exception."""
    
    def __init__(self, message: str = "Dependency error", dependency_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.DEPENDENCY_ERROR, **kwargs)
        self.dependency_name = dependency_name
        if dependency_name:
            self.details['dependency_name'] = dependency_name


class IntegrationCircuitBreakerException(IntegrationException):
    """Integration circuit breaker exception."""
    
    def __init__(self, message: str = "Circuit breaker is open", circuit_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.CIRCUIT_BREAKER_ERROR, **kwargs)
        self.circuit_name = circuit_name
        if circuit_name:
            self.details['circuit_name'] = circuit_name


class IntegrationWebhookException(IntegrationException):
    """Integration webhook exception."""
    
    def __init__(self, message: str = "Webhook error", webhook_url: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.WEBHOOK_ERROR, **kwargs)
        self.webhook_url = webhook_url
        if webhook_url:
            self.details['webhook_url'] = webhook_url


class IntegrationQueueException(IntegrationException):
    """Integration queue exception."""
    
    def __init__(self, message: str = "Queue error", queue_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.QUEUE_ERROR, **kwargs)
        self.queue_name = queue_name
        if queue_name:
            self.details['queue_name'] = queue_name


class IntegrationBridgeException(IntegrationException):
    """Integration bridge exception."""
    
    def __init__(self, message: str = "Bridge error", bridge_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.BRIDGE_ERROR, **kwargs)
        self.bridge_name = bridge_name
        if bridge_name:
            self.details['bridge_name'] = bridge_name


class IntegrationEventBusException(IntegrationException):
    """Integration event bus exception."""
    
    def __init__(self, message: str = "Event bus error", event_type: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.EVENT_BUS_ERROR, **kwargs)
        self.event_type = event_type
        if event_type:
            self.details['event_type'] = event_type


class IntegrationValidatorException(IntegrationException):
    """Integration validator exception."""
    
    def __init__(self, message: str = "Validator error", validator_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.VALIDATOR_ERROR, **kwargs)
        self.validator_name = validator_name
        if validator_name:
            self.details['validator_name'] = validator_name


class IntegrationSecurityException(IntegrationException):
    """Integration security exception."""
    
    def __init__(self, message: str = "Security error", security_type: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.SECURITY_ERROR, IntegrationSeverity.HIGH, **kwargs)
        self.security_type = security_type
        if security_type:
            self.details['security_type'] = security_type


class IntegrationCacheException(IntegrationException):
    """Integration cache exception."""
    
    def __init__(self, message: str = "Cache error", cache_key: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.CACHE_ERROR, **kwargs)
        self.cache_key = cache_key
        if cache_key:
            self.details['cache_key'] = cache_key


class IntegrationDatabaseException(IntegrationException):
    """Integration database exception."""
    
    def __init__(self, message: str = "Database error", table_name: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.DATABASE_ERROR, **kwargs)
        self.table_name = table_name
        if table_name:
            self.details['table_name'] = table_name


class IntegrationFileSystemException(IntegrationException):
    """Integration file system exception."""
    
    def __init__(self, message: str = "File system error", file_path: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.FILE_SYSTEM_ERROR, **kwargs)
        self.file_path = file_path
        if file_path:
            self.details['file_path'] = file_path


class IntegrationEncryptionException(IntegrationException):
    """Integration encryption exception."""
    
    def __init__(self, message: str = "Encryption error", algorithm: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.ENCRYPTION_ERROR, **kwargs)
        self.algorithm = algorithm
        if algorithm:
            self.details['algorithm'] = algorithm


class IntegrationDecryptionException(IntegrationException):
    """Integration decryption exception."""
    
    def __init__(self, message: str = "Decryption error", algorithm: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.DECRYPTION_ERROR, **kwargs)
        self.algorithm = algorithm
        if algorithm:
            self.details['algorithm'] = algorithm


class IntegrationNetworkException(IntegrationException):
    """Integration network exception."""
    
    def __init__(self, message: str = "Network error", network_type: str = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.NETWORK_ERROR, **kwargs)
        self.network_type = network_type
        if network_type:
            self.details['network_type'] = network_type


class IntegrationInternalServerException(IntegrationException):
    """Integration internal server exception."""
    
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message, IntegrationErrorCode.INTERNAL_SERVER_ERROR, IntegrationSeverity.HIGH, **kwargs)


class IntegrationUnknownException(IntegrationException):
    """Integration unknown exception."""
    
    def __init__(self, message: str = "Unknown error", original_exception: Exception = None, **kwargs):
        super().__init__(message, IntegrationErrorCode.UNKNOWN_ERROR, **kwargs)
        self.original_exception = original_exception
        if original_exception:
            self.details['original_exception'] = str(original_exception)


class ExceptionHandler:
    """
    Exception handler for integration system.
    
    Provides centralized exception handling,
    logging, and error reporting.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.error_counts = {}
        self.error_history = []
    
    def handle_exception(self, exception: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle exception.
        
        Args:
            exception: Exception to handle
            context: Exception context
            
        Returns:
            Error response
        """
        context = context or {}
        
        # Convert to integration exception if needed
        if not isinstance(exception, IntegrationException):
            integration_exception = IntegrationUnknownException(
                message=str(exception),
                original_exception=exception
            )
        else:
            integration_exception = exception
        
        # Log exception
        self._log_exception(integration_exception, context)
        
        # Update statistics
        self._update_statistics(integration_exception)
        
        # Create error response
        error_response = {
            'success': False,
            'error': {
                'code': integration_exception.error_code.value,
                'message': integration_exception.message,
                'severity': integration_exception.severity.value,
                'timestamp': integration_exception.timestamp.isoformat(),
                'traceback_id': integration_exception.traceback_id,
                'details': integration_exception.details,
            }
        }
        
        # Add context if provided
        if context:
            error_response['context'] = context
        
        return error_response
    
    def _log_exception(self, exception: IntegrationException, context: Dict[str, Any]):
        """Log exception with appropriate level."""
        log_message = f"[{exception.error_code.value}] {exception.message}"
        
        if exception.severity == IntegrationSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=exception, extra={'context': context})
        elif exception.severity == IntegrationSeverity.HIGH:
            self.logger.error(log_message, exc_info=exception, extra={'context': context})
        elif exception.severity == IntegrationSeverity.MEDIUM:
            self.logger.warning(log_message, exc_info=exception, extra={'context': context})
        else:
            self.logger.info(log_message, exc_info=exception, extra={'context': context})
    
    def _update_statistics(self, exception: IntegrationException):
        """Update exception statistics."""
        error_code = exception.error_code.value
        
        # Update counts
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        
        # Add to history
        self.error_history.append({
            'error_code': error_code,
            'message': exception.message,
            'severity': exception.severity.value,
            'timestamp': exception.timestamp.isoformat(),
            'traceback_id': exception.traceback_id,
        })
        
        # Keep only last 1000 errors
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get exception statistics."""
        total_errors = sum(self.error_counts.values())
        
        # Count by severity
        severity_counts = {}
        for error in self.error_history:
            severity = error['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by error code
        error_code_counts = dict(self.error_counts)
        
        return {
            'total_errors': total_errors,
            'error_code_counts': error_code_counts,
            'severity_counts': severity_counts,
            'recent_errors': self.error_history[-10:],  # Last 10 errors
        }
    
    def get_error_rate(self, window_minutes: int = 60) -> float:
        """Get error rate for time window."""
        cutoff_time = timezone.now() - timedelta(minutes=window_minutes)
        
        recent_errors = [
            error for error in self.error_history
            if datetime.fromisoformat(error['timestamp']) >= cutoff_time
        ]
        
        return len(recent_errors) / window_minutes  # Errors per minute


# Global exception handler
exception_handler = ExceptionHandler()


# Decorators for exception handling
def handle_integration_exceptions(default_response: Dict[str, Any] = None):
    """
    Decorator for handling integration exceptions.
    
    Args:
        default_response: Default response on exception
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args),
                    'kwargs': str(kwargs)
                }
                return exception_handler.handle_exception(e, context) or default_response or {
                    'success': False,
                    'error': 'Internal error occurred'
                }
        return wrapper
    return decorator


def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying functions on exception.
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff: Backoff multiplier
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except IntegrationException as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break
                    
                    # Don't retry on certain exceptions
                    if e.error_code in [
                        IntegrationErrorCode.AUTHENTICATION_ERROR,
                        IntegrationErrorCode.AUTHORIZATION_ERROR,
                        IntegrationErrorCode.VALIDATION_ERROR,
                        IntegrationErrorCode.CONFIGURATION_ERROR,
                    ]:
                        break
                    
                    logger.warning(f"Retrying function {func.__name__} after error: {e.message}")
                    time.sleep(current_delay)
                    current_delay *= backoff
                except Exception as e:
                    last_exception = e
                    break
            
            # Handle the final exception
            context = {
                'function': func.__name__,
                'attempts': max_retries + 1,
                'final_attempt': True
            }
            
            return exception_handler.handle_exception(last_exception, context)
        return wrapper
    return decorator


# Convenience functions
def handle_exception(exception: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handle exception using global handler."""
    return exception_handler.handle_exception(exception, context)


def get_exception_statistics() -> Dict[str, Any]:
    """Get exception statistics."""
    return exception_handler.get_statistics()


def get_error_rate(window_minutes: int = 60) -> float:
    """Get error rate for time window."""
    return exception_handler.get_error_rate(window_minutes)


# Error message templates
ERROR_MESSAGES = {
    IntegrationErrorCode.GENERAL_ERROR: "An error occurred",
    IntegrationErrorCode.CONFIGURATION_ERROR: "Configuration error",
    IntegrationErrorCode.VALIDATION_ERROR: "Validation failed",
    IntegrationErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
    IntegrationErrorCode.AUTHORIZATION_ERROR: "Authorization failed",
    IntegrationErrorCode.CONNECTION_ERROR: "Connection failed",
    IntegrationErrorCode.TIMEOUT_ERROR: "Request timed out",
    IntegrationErrorCode.NETWORK_ERROR: "Network error",
    IntegrationErrorCode.PROTOCOL_ERROR: "Protocol error",
    IntegrationErrorCode.DATA_FORMAT_ERROR: "Invalid data format",
    IntegrationErrorCode.TRANSFORMATION_ERROR: "Data transformation failed",
    IntegrationErrorCode.ENCRYPTION_ERROR: "Encryption failed",
    IntegrationErrorCode.DECRYPTION_ERROR: "Decryption failed",
    IntegrationErrorCode.VERSION_MISMATCH_ERROR: "Version mismatch",
    IntegrationErrorCode.RATE_LIMIT_ERROR: "Rate limit exceeded",
    IntegrationErrorCode.QUOTA_EXCEEDED_ERROR: "Quota exceeded",
    IntegrationErrorCode.SERVICE_UNAVAILABLE_ERROR: "Service unavailable",
    IntegrationErrorCode.INTERNAL_SERVER_ERROR: "Internal server error",
    IntegrationErrorCode.DEPENDENCY_ERROR: "Dependency error",
    IntegrationErrorCode.CIRCUIT_BREAKER_ERROR: "Circuit breaker open",
    IntegrationErrorCode.WEBHOOK_ERROR: "Webhook error",
    IntegrationErrorCode.QUEUE_ERROR: "Queue error",
    IntegrationErrorCode.BRIDGE_ERROR: "Bridge error",
    IntegrationErrorCode.EVENT_BUS_ERROR: "Event bus error",
    IntegrationErrorCode.VALIDATOR_ERROR: "Validator error",
    IntegrationErrorCode.SECURITY_ERROR: "Security error",
    IntegrationErrorCode.CACHE_ERROR: "Cache error",
    IntegrationErrorCode.DATABASE_ERROR: "Database error",
    IntegrationErrorCode.FILE_SYSTEM_ERROR: "File system error",
    IntegrationErrorCode.UNKNOWN_ERROR: "Unknown error",
}


def get_error_message(error_code: IntegrationErrorCode) -> str:
    """Get error message for error code."""
    return ERROR_MESSAGES.get(error_code, "Unknown error")


def create_exception(error_code: IntegrationErrorCode, message: str = None, **kwargs) -> IntegrationException:
    """Create integration exception."""
    if not message:
        message = get_error_message(error_code)
    
    exception_class = {
        IntegrationErrorCode.TIMEOUT_ERROR: IntegrationTimeoutException,
        IntegrationErrorCode.CONNECTION_ERROR: IntegrationConnectionException,
        IntegrationErrorCode.AUTHENTICATION_ERROR: IntegrationAuthenticationException,
        IntegrationErrorCode.AUTHORIZATION_ERROR: IntegrationAuthorizationException,
        IntegrationErrorCode.VALIDATION_ERROR: IntegrationValidationException,
        IntegrationErrorCode.CONFIGURATION_ERROR: IntegrationConfigurationException,
        IntegrationErrorCode.PROTOCOL_ERROR: IntegrationProtocolException,
        IntegrationErrorCode.DATA_FORMAT_ERROR: IntegrationDataFormatException,
        IntegrationErrorCode.TRANSFORMATION_ERROR: IntegrationTransformationException,
        IntegrationErrorCode.VERSION_MISMATCH_ERROR: IntegrationVersionMismatchException,
        IntegrationErrorCode.RATE_LIMIT_ERROR: IntegrationRateLimitException,
        IntegrationErrorCode.QUOTA_EXCEEDED_ERROR: IntegrationQuotaExceededException,
        IntegrationErrorCode.SERVICE_UNAVAILABLE_ERROR: IntegrationServiceUnavailableException,
        IntegrationErrorCode.DEPENDENCY_ERROR: IntegrationDependencyException,
        IntegrationErrorCode.CIRCUIT_BREAKER_ERROR: IntegrationCircuitBreakerException,
        IntegrationErrorCode.WEBHOOK_ERROR: IntegrationWebhookException,
        IntegrationErrorCode.QUEUE_ERROR: IntegrationQueueException,
        IntegrationErrorCode.BRIDGE_ERROR: IntegrationBridgeException,
        IntegrationErrorCode.EVENT_BUS_ERROR: IntegrationEventBusException,
        IntegrationErrorCode.VALIDATOR_ERROR: IntegrationValidatorException,
        IntegrationErrorCode.SECURITY_ERROR: IntegrationSecurityException,
        IntegrationErrorCode.CACHE_ERROR: IntegrationCacheException,
        IntegrationErrorCode.DATABASE_ERROR: IntegrationDatabaseException,
        IntegrationErrorCode.FILE_SYSTEM_ERROR: IntegrationFileSystemException,
        IntegrationErrorCode.ENCRYPTION_ERROR: IntegrationEncryptionException,
        IntegrationErrorCode.DECRYPTION_ERROR: IntegrationDecryptionException,
        IntegrationErrorCode.NETWORK_ERROR: IntegrationNetworkException,
        IntegrationErrorCode.INTERNAL_SERVER_ERROR: IntegrationInternalServerException,
        IntegrationErrorCode.UNKNOWN_ERROR: IntegrationUnknownException,
    }.get(error_code, IntegrationException)
    
    return exception_class(message, error_code, **kwargs)

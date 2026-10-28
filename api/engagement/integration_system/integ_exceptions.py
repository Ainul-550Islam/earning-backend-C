# engagement/integration_system/integ_exceptions.py
"""
Custom exceptions for integration system.
Provides specific exception classes for different error scenarios.
"""
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback
from datetime import datetime

from django.utils import timezone
from .integ_constants import ERROR_CODES

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Error context information."""
    integration_id: Optional[str] = None
    integration_type: Optional[str] = None
    operation: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


class IntegrationException(Exception):
    """Base integration exception."""
    
    def __init__(self, message: str, error_code: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "INT_000"
        self.context = context or ErrorContext()
        self.cause = cause
        self.severity = ErrorSeverity.MEDIUM
        
        if cause:
            self.context.stack_trace = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'severity': self.severity.value,
            'context': {
                'integration_id': self.context.integration_id,
                'integration_type': self.context.integration_type,
                'operation': self.context.operation,
                'user_id': self.context.user_id,
                'request_id': self.context.request_id,
                'timestamp': self.context.timestamp.isoformat(),
                'metadata': self.context.metadata,
                'stack_trace': self.context.stack_trace
            },
            'cause': str(self.cause) if self.cause else None
        }


class ConfigurationError(IntegrationException):
    """Configuration related errors."""
    
    def __init__(self, message: str, config_key: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['INVALID_CONFIGURATION'], context, cause)
        self.config_key = config_key
        self.severity = ErrorSeverity.HIGH


class ConnectionError(IntegrationException):
    """Connection related errors."""
    
    def __init__(self, message: str, endpoint: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['CONNECTION_FAILED'], context, cause)
        self.endpoint = endpoint
        self.severity = ErrorSeverity.HIGH


class AuthenticationError(IntegrationException):
    """Authentication related errors."""
    
    def __init__(self, message: str, auth_type: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['AUTHENTICATION_FAILED'], context, cause)
        self.auth_type = auth_type
        self.severity = ErrorSeverity.HIGH


class AuthorizationError(IntegrationException):
    """Authorization related errors."""
    
    def __init__(self, message: str, permission: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['PERMISSION_DENIED'], context, cause)
        self.permission = permission
        self.severity = ErrorSeverity.HIGH


class DataValidationError(IntegrationException):
    """Data validation related errors."""
    
    def __init__(self, message: str, field: str = None, 
                 validation_errors: List[str] = None,
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['DATA_VALIDATION_FAILED'], context, cause)
        self.field = field
        self.validation_errors = validation_errors or []
        self.severity = ErrorSeverity.MEDIUM


class TimeoutError(IntegrationException):
    """Timeout related errors."""
    
    def __init__(self, message: str, timeout_seconds: int = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['TIMEOUT_EXCEEDED'], context, cause)
        self.timeout_seconds = timeout_seconds
        self.severity = ErrorSeverity.MEDIUM


class RateLimitError(IntegrationException):
    """Rate limiting related errors."""
    
    def __init__(self, message: str, limit: int = None, window: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['RATE_LIMIT_EXCEEDED'], context, cause)
        self.limit = limit
        self.window = window
        self.severity = ErrorSeverity.MEDIUM


class CircuitBreakerError(IntegrationException):
    """Circuit breaker related errors."""
    
    def __init__(self, message: str, circuit_state: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['CIRCUIT_BREAKER_OPEN'], context, cause)
        self.circuit_state = circuit_state
        self.severity = ErrorSeverity.HIGH


class TransformationError(IntegrationException):
    """Data transformation related errors."""
    
    def __init__(self, message: str, source_format: str = None, 
                 target_format: str = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, ERROR_CODES['TRANSFORMATION_FAILED'], context, cause)
        self.source_format = source_format
        self.target_format = target_format
        self.severity = ErrorSeverity.MEDIUM


class VersionMismatchError(IntegrationException):
    """Version compatibility related errors."""
    
    def __init__(self, message: str, current_version: str = None, 
                 required_version: str = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, ERROR_CODES['VERSION_MISMATCH'], context, cause)
        self.current_version = current_version
        self.required_version = required_version
        self.severity = ErrorSeverity.MEDIUM


class DependencyError(IntegrationException):
    """Dependency related errors."""
    
    def __init__(self, message: str, dependency: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['DEPENDENCY_FAILED'], context, cause)
        self.dependency = dependency
        self.severity = ErrorSeverity.HIGH


class DataCorruptionError(IntegrationException):
    """Data corruption related errors."""
    
    def __init__(self, message: str, data_id: str = None, 
                 checksum: str = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, ERROR_CODES['DATA_CORRUPTION'], context, cause)
        self.data_id = data_id
        self.checksum = checksum
        self.severity = ErrorSeverity.CRITICAL


class SystemOverloadError(IntegrationException):
    """System overload related errors."""
    
    def __init__(self, message: str, load_type: str = None, 
                 current_load: int = None, max_capacity: int = None,
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['SYSTEM_OVERLOADED'], context, cause)
        self.load_type = load_type
        self.current_load = current_load
        self.max_capacity = max_capacity
        self.severity = ErrorSeverity.HIGH


class MaintenanceModeError(IntegrationException):
    """Maintenance mode related errors."""
    
    def __init__(self, message: str, maintenance_type: str = None, 
                 estimated_downtime: int = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, ERROR_CODES['MAINTENANCE_MODE'], context, cause)
        self.maintenance_type = maintenance_type
        self.estimated_downtime = estimated_downtime
        self.severity = ErrorSeverity.MEDIUM


class WebhookError(IntegrationException):
    """Webhook related errors."""
    
    def __init__(self, message: str, webhook_id: str = None, 
                 event_type: str = None, status_code: int = None,
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, "WEBHOOK_ERROR", context, cause)
        self.webhook_id = webhook_id
        self.event_type = event_type
        self.status_code = status_code
        self.severity = ErrorSeverity.MEDIUM


class BridgeError(IntegrationException):
    """Bridge related errors."""
    
    def __init__(self, message: str, bridge_id: str = None, 
                 bridge_type: str = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, "BRIDGE_ERROR", context, cause)
        self.bridge_id = bridge_id
        self.bridge_type = bridge_type
        self.severity = ErrorSeverity.HIGH


class QueueError(IntegrationException):
    """Message queue related errors."""
    
    def __init__(self, message: str, queue_name: str = None, 
                 queue_size: int = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, "QUEUE_ERROR", context, cause)
        self.queue_name = queue_name
        self.queue_size = queue_size
        self.severity = ErrorSeverity.HIGH


class SecurityAlertError(IntegrationException):
    """Security alert related errors."""
    
    def __init__(self, message: str, alert_type: str = None, 
                 threat_level: str = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, "SECURITY_ALERT", context, cause)
        self.alert_type = alert_type
        self.threat_level = threat_level
        self.severity = ErrorSeverity.CRITICAL


class RetryExhaustedError(IntegrationException):
    """Retry exhausted error."""
    
    def __init__(self, message: str, max_retries: int = None, 
                 attempt_count: int = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, "RETRY_EXHAUSTED", context, cause)
        self.max_retries = max_retries
        self.attempt_count = attempt_count
        self.severity = ErrorSeverity.HIGH


class IntegrationNotFoundError(IntegrationException):
    """Integration not found error."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 context: ErrorContext = None, cause: Exception = None):
        super().__init__(message, ERROR_CODES['INTEGRATION_NOT_FOUND'], context, cause)
        self.integration_id = integration_id
        self.severity = ErrorSeverity.MEDIUM


class ValidationError(IntegrationException):
    """General validation error."""
    
    def __init__(self, message: str, field: str = None, 
                 value: Any = None, context: ErrorContext = None, 
                 cause: Exception = None):
        super().__init__(message, "VALIDATION_ERROR", context, cause)
        self.field = field
        self.value = value
        self.severity = ErrorSeverity.MEDIUM


# Exception utilities
class ExceptionUtils:
    """Utilities for exception handling."""
    
    @staticmethod
    def create_context(integration_id: str = None, integration_type: str = None,
                       operation: str = None, user_id: str = None, 
                       request_id: str = None, **metadata) -> ErrorContext:
        """Create error context."""
        return ErrorContext(
            integration_id=integration_id,
            integration_type=integration_type,
            operation=operation,
            user_id=user_id,
            request_id=request_id,
            metadata=metadata
        )
    
    @staticmethod
    def log_exception(exception: IntegrationException, logger_instance: logging.Logger = None):
        """Log exception with context."""
        log_logger = logger_instance or logger
        
        if exception.severity == ErrorSeverity.CRITICAL:
            log_logger.critical(f"Critical integration error: {exception.message}", exc_info=exception)
        elif exception.severity == ErrorSeverity.HIGH:
            log_logger.error(f"High severity integration error: {exception.message}", exc_info=exception)
        elif exception.severity == ErrorSeverity.MEDIUM:
            log_logger.warning(f"Medium severity integration error: {exception.message}", exc_info=exception)
        else:
            log_logger.info(f"Low severity integration error: {exception.message}", exc_info=exception)
    
    @staticmethod
    def wrap_exception(func):
        """Decorator to wrap exceptions in IntegrationException."""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrationException:
                raise
            except Exception as exc:
                # Wrap unknown exceptions
                context = ExceptionUtils.create_context(
                    operation=func.__name__,
                    metadata={'args': str(args), 'kwargs': str(kwargs)}
                )
                raise IntegrationException(
                    f"Unexpected error in {func.__name__}: {str(exc)}",
                    context=context,
                    cause=exc
                )
        return wrapper
    
    @staticmethod
    def handle_exception(exception: Exception, default_return=None, 
                        logger_instance: logging.Logger = None):
        """Handle exception gracefully."""
        if isinstance(exception, IntegrationException):
            ExceptionUtils.log_exception(exception, logger_instance)
            return default_return
        else:
            # Wrap unknown exception
            context = ExceptionUtils.create_context(
                operation="unknown",
                metadata={'exception_type': type(exception).__name__}
            )
            wrapped_exception = IntegrationException(
                f"Unexpected error: {str(exception)}",
                context=context,
                cause=exception
            )
            ExceptionUtils.log_exception(wrapped_exception, logger_instance)
            return default_return
    
    @staticmethod
    def create_error_response(exception: IntegrationException) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            'success': False,
            'error': {
                'type': exception.__class__.__name__,
                'message': exception.message,
                'code': exception.error_code,
                'severity': exception.severity.value,
                'context': exception.context.__dict__
            }
        }
    
    @staticmethod
    def is_retryable(exception: IntegrationException) -> bool:
        """Check if exception is retryable."""
        retryable_exceptions = [
            TimeoutError,
            ConnectionError,
            RateLimitError,
            SystemOverloadError,
            MaintenanceModeError,
            WebhookError,
            QueueError
        ]
        
        return type(exception) in retryable_exceptions
    
    @staticmethod
    def get_retry_delay(exception: IntegrationException, attempt: int = 1) -> int:
        """Get retry delay for exception."""
        if isinstance(exception, RateLimitError):
            return exception.window or 60
        elif isinstance(exception, TimeoutError):
            return min(300, 30 * (2 ** attempt))  # Exponential backoff
        elif isinstance(exception, ConnectionError):
            return min(60, 5 * (2 ** attempt))  # Exponential backoff
        else:
            return 30  # Default retry delay


# Exception handler class
class ExceptionHandler:
    """Central exception handler."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ExceptionHandler")
        self.error_counts = {}
        self.error_patterns = {}
    
    def handle_exception(self, exception: Exception, context: ErrorContext = None,
                        default_return=None, reraise: bool = False):
        """Handle exception with logging and optional reraise."""
        try:
            # Wrap unknown exceptions
            if not isinstance(exception, IntegrationException):
                context = context or ExceptionUtils.create_context()
                exception = IntegrationException(
                    f"Unhandled exception: {str(exception)}",
                    context=context,
                    cause=exception
                )
            
            # Log exception
            ExceptionUtils.log_exception(exception, self.logger)
            
            # Track error counts
            error_type = exception.__class__.__name__
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            
            # Check if we should reraise
            if reraise:
                raise exception
            
            return default_return
            
        except Exception as exc:
            self.logger.error(f"Exception handler failed: {exc}")
            if reraise:
                raise exc
            return default_return
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts': self.error_counts.copy(),
            'most_common_error': max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None,
            'last_updated': timezone.now().isoformat()
        }
    
    def reset_statistics(self):
        """Reset error statistics."""
        self.error_counts.clear()
        self.error_patterns.clear()
    
    def is_error_pattern(self, exception: IntegrationException) -> bool:
        """Check if exception matches known pattern."""
        error_type = exception.__class__.__name__
        error_message = exception.message.lower()
        
        # Check for common patterns
        patterns = {
            'timeout': ['timeout', 'timed out'],
            'connection': ['connection', 'connect', 'network'],
            'authentication': ['auth', 'unauthorized', 'forbidden'],
            'validation': ['validation', 'invalid', 'required'],
            'rate_limit': ['rate limit', 'too many requests'],
            'data': ['data', 'corrupt', 'invalid data'],
            'version': ['version', 'compatible', 'mismatch'],
        }
        
        for pattern_name, keywords in patterns.items():
            if any(keyword in error_message for keyword in keywords):
                return True
        
        return False


# Global exception handler instance
exception_handler = ExceptionHandler()


# Decorators
def handle_exceptions(default_return=None, reraise: bool = False):
    """Decorator to handle exceptions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                return exception_handler.handle_exception(
                    exc, 
                    default_return=default_return, 
                    reraise=True
                )
        return wrapper
    return decorator


def integration_error(error_code: str = None, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
    """Decorator to create integration exceptions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                context = ExceptionUtils.create_context(
                    operation=func.__name__,
                    metadata={'args': str(args), 'kwargs': str(kwargs)}
                )
                raise IntegrationException(
                    f"Error in {func.__name__}: {str(exc)}",
                    error_code=error_code,
                    severity=severity,
                    context=context,
                    cause=exc
                )
        return wrapper
    return decorator


def retry_on_exception(max_retries: int = 3, delay: int = 1):
    """Decorator to retry on exceptions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    
                    if attempt == max_retries:
                        # Last attempt, raise the exception
                        break
                    
                    # Check if exception is retryable
                    if isinstance(exc, IntegrationException):
                        if not ExceptionUtils.is_retryable(exc):
                            break
                    
                        # Get retry delay
                        retry_delay = ExceptionUtils.get_retry_delay(exc, attempt)
                        time.sleep(retry_delay)
                    else:
                        # Unknown exception, don't retry
                        break
            
            # Re-raise the last exception
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# Context manager for exception handling
class ExceptionContext:
    """Context manager for exception handling."""
    
    def __init__(self, context: ErrorContext = None, 
                 default_return=None, reraise: bool = False):
        self.context = context
        self.default_return = default_return
        self. reraise = reraise
        self.logger = logging.getLogger(f"{__name__}.ExceptionContext")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            return exception_handler.handle_exception(
                exc_val,
                self.context,
                self.default_return,
                self. reraise
            )
        return False


# Exception factory functions
def create_configuration_error(message: str, config_key: str = None, 
                            context: ErrorContext = None) -> ConfigurationError:
    """Create configuration error."""
    return ConfigurationError(message, config_key, context)


def create_connection_error(message: str, endpoint: str = None, 
                          context: ErrorContext = None) -> ConnectionError:
    """Create connection error."""
    return ConnectionError(message, endpoint, context)


def create_authentication_error(message: str, auth_type: str = None, 
                              context: ErrorContext = None) -> AuthenticationError:
    """Create authentication error."""
    return AuthenticationError(message, auth_type, context)


def create_authorization_error(message: str, permission: str = None, 
                              context: ErrorContext = None) -> AuthorizationError:
    """Create authorization error."""
    return AuthorizationError(message, permission, context)


def create_timeout_error(message: str, timeout_seconds: int = None, 
                        context: ErrorContext = None) -> TimeoutError:
    """Create timeout error."""
    return TimeoutError(message, timeout_seconds, context)


def create_rate_limit_error(message: str, limit: int = None, 
                            window: str = None, context: ErrorContext = None) -> RateLimitError:
    """Create rate limit error."""
    return RateLimitError(message, limit, window, context)


def create_circuit_breaker_error(message: str, circuit_state: str = None, 
                                 context: ErrorContext = None) -> CircuitBreakerError:
    """Create circuit breaker error."""
    return CircuitBreakerError(message, circuit_state, context)

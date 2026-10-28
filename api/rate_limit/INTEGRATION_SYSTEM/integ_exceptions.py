"""
Integration Exceptions - Custom Exception Classes

Custom exception classes for the integration system with detailed
error information and proper error handling.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories."""
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    CIRCUIT_BREAKER = "circuit_breaker"
    DATA_PROCESSING = "data_processing"
    SYSTEM = "system"
    BUSINESS_LOGIC = "business_logic"
    INTEGRATION = "integration"


@dataclass
class ErrorContext:
    """Error context information."""
    component: str
    operation: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorDetails:
    """Detailed error information."""
    error_code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: ErrorContext
    cause: Optional[Exception] = None
    stack_trace: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    retry_after: Optional[int] = None  # seconds
    additional_data: Dict[str, Any] = field(default_factory=dict)


class IntegrationError(Exception):
    """Base exception for integration system."""
    
    def __init__(self, message: str, error_code: str = "INTEGRATION_ERROR",
                 category: ErrorCategory = ErrorCategory.INTEGRATION,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: ErrorContext = None,
                 cause: Exception = None,
                 **kwargs):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext(component="unknown", operation="unknown")
        self.cause = cause
        self.suggestions = kwargs.get('suggestions', [])
        self.retry_after = kwargs.get('retry_after')
        self.additional_data = {k: v for k, v in kwargs.items() 
                             if k not in ['suggestions', 'retry_after']}
        
        # Log the error
        self._log_error()
    
    def _log_error(self):
        """Log the error with appropriate level."""
        log_message = f"[{self.error_code}] {self.message}"
        log_data = {
            'error_code': self.error_code,
            'category': self.category.value,
            'severity': self.severity.value,
            'component': self.context.component,
            'operation': self.context.operation,
            'request_id': self.context.request_id,
            'user_id': self.context.user_id,
            'ip_address': self.context.ip_address,
            'timestamp': self.context.timestamp.isoformat()
        }
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra=log_data)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(log_message, extra=log_data)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message, extra=log_data)
        else:
            logger.info(log_message, extra=log_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': {
                'component': self.context.component,
                'operation': self.context.operation,
                'request_id': self.context.request_id,
                'user_id': self.context.user_id,
                'ip_address': self.context.ip_address,
                'timestamp': self.context.timestamp.isoformat(),
                'metadata': self.context.metadata
            },
            'suggestions': self.suggestions,
            'retry_after': self.retry_after,
            'additional_data': self.additional_data
        }
    
    @classmethod
    def from_exception(cls, exception: Exception, message: str = None, 
                      error_code: str = None, **kwargs) -> 'IntegrationError':
        """Create IntegrationError from another exception."""
        if isinstance(exception, IntegrationError):
            return exception
        
        error_message = message or str(exception)
        error_code = error_code or f"WRAPPED_{type(exception).__name__.upper()}"
        
        return cls(
            message=error_message,
            error_code=error_code,
            cause=exception,
            **kwargs
        )


class NetworkError(IntegrationError):
    """Network-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Check network connectivity",
                "Verify target service is available",
                "Check firewall settings"
            ],
            **kwargs
        )


class AuthenticationError(IntegrationError):
    """Authentication-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Check authentication credentials",
                "Verify API key validity",
                "Check token expiration"
            ],
            **kwargs
        )


class AuthorizationError(IntegrationError):
    """Authorization-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Check user permissions",
                "Verify access rights",
                "Contact administrator for access"
            ],
            **kwargs
        )


class ValidationError(IntegrationError):
    """Data validation errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check data format",
                "Verify required fields",
                "Review validation rules"
            ],
            **kwargs
        )


class ConfigurationError(IntegrationError):
    """Configuration-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Check configuration settings",
                "Verify environment variables",
                "Review configuration documentation"
            ],
            **kwargs
        )


class TimeoutError(IntegrationError):
    """Timeout-related errors."""
    
    def __init__(self, message: str, timeout_seconds: int = None, **kwargs):
        super().__init__(
            message=message,
            error_code="TIMEOUT_ERROR",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            retry_after=timeout_seconds or 30,
            suggestions=[
                "Increase timeout value",
                "Check network latency",
                "Optimize request processing"
            ],
            **kwargs
        )


class RateLimitError(IntegrationError):
    """Rate limiting errors."""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            retry_after=retry_after or 60,
            suggestions=[
                "Reduce request frequency",
                "Implement exponential backoff",
                "Check rate limit quotas"
            ],
            **kwargs
        )


class CircuitBreakerError(IntegrationError):
    """Circuit breaker errors."""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CIRCUIT_BREAKER_ERROR",
            category=ErrorCategory.CIRCUIT_BREAKER,
            severity=ErrorSeverity.HIGH,
            retry_after=retry_after or 60,
            suggestions=[
                "Wait for circuit breaker to recover",
                "Check upstream service health",
                "Implement fallback mechanisms"
            ],
            **kwargs
        )


class DataProcessingError(IntegrationError):
    """Data processing errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="DATA_PROCESSING_ERROR",
            category=ErrorCategory.DATA_PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check data format",
                "Verify data transformation rules",
                "Review processing logic"
            ],
            **kwargs
        )


class SystemError(IntegrationError):
    """System-level errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="SYSTEM_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            suggestions=[
                "Check system resources",
                "Review system logs",
                "Contact system administrator"
            ],
            **kwargs
        )


class BusinessLogicError(IntegrationError):
    """Business logic errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Review business rules",
                "Check data consistency",
                "Verify business constraints"
            ],
            **kwargs
        )


class WebhookError(IntegrationError):
    """Webhook-specific errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="WEBHOOK_ERROR",
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check webhook URL",
                "Verify webhook secret",
                "Review webhook payload format"
            ],
            **kwargs
        )


class WebhookTimeoutError(WebhookError):
    """Webhook timeout errors."""
    
    def __init__(self, message: str, timeout_seconds: int = None, **kwargs):
        super().__init__(
            message=message,
            retry_after=timeout_seconds or 30,
            **kwargs
        )


class BridgeError(IntegrationError):
    """Bridge system errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="BRIDGE_ERROR",
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check bridge configuration",
                "Verify bridge connectivity",
                "Review bridge routing rules"
            ],
            **kwargs
        )


class BridgeTimeoutError(BridgeError):
    """Bridge timeout errors."""
    
    def __init__(self, message: str, timeout_seconds: int = None, **kwargs):
        super().__init__(
            message=message,
            retry_after=timeout_seconds or 30,
            **kwargs
        )


class EventBusError(IntegrationError):
    """Event bus errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="EVENT_BUS_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check event bus configuration",
                "Verify event handlers",
                "Review event queue status"
            ],
            **kwargs
        )


class TransformationError(IntegrationError):
    """Data transformation errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="TRANSFORMATION_ERROR",
            category=ErrorCategory.DATA_PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check transformation rules",
                "Verify data format compatibility",
                "Review field mappings"
            ],
            **kwargs
        )


class VersioningError(IntegrationError):
    """Version management errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="VERSIONING_ERROR",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check version compatibility",
                "Verify version format",
                "Review migration scripts"
            ],
            **kwargs
        )


class MessageQueueError(IntegrationError):
    """Message queue errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="MESSAGE_QUEUE_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check queue configuration",
                "Verify queue capacity",
                "Review message processing logic"
            ],
            **kwargs
        )


class DataBridgeError(IntegrationError):
    """Data bridge errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="DATA_BRIDGE_ERROR",
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check bridge configuration",
                "Verify data mappings",
                "Review sync rules"
            ],
            **kwargs
        )


class RegistrationError(IntegrationError):
    """Service registration errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="REGISTRATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check service configuration",
                "Verify service dependencies",
                "Review registration requirements"
            ],
            **kwargs
        )


class HealthCheckError(IntegrationError):
    """Health check errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="HEALTH_CHECK_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.LOW,
            suggestions=[
                "Check service status",
                "Review health check configuration",
                "Verify service dependencies"
            ],
            **kwargs
        )


class ErrorUtils:
    """Utility functions for error handling."""
    
    @staticmethod
    def create_error_context(component: str, operation: str, **kwargs) -> ErrorContext:
        """Create error context."""
        return ErrorContext(
            component=component,
            operation=operation,
            request_id=kwargs.get('request_id'),
            user_id=kwargs.get('user_id'),
            ip_address=kwargs.get('ip_address'),
            metadata=kwargs.get('metadata', {})
        )
    
    @staticmethod
    def wrap_exception(exception: Exception, component: str, operation: str, 
                      message: str = None, **kwargs) -> IntegrationError:
        """Wrap an exception in IntegrationError."""
        context = ErrorUtils.create_error_context(component, operation, **kwargs)
        
        # Determine appropriate exception type based on original exception
        if isinstance(exception, (ConnectionError, OSError)):
            return NetworkError(message or str(exception), context=context, cause=exception, **kwargs)
        elif 'timeout' in str(exception).lower():
            return TimeoutError(message or str(exception), context=context, cause=exception, **kwargs)
        elif 'validation' in str(exception).lower():
            return ValidationError(message or str(exception), context=context, cause=exception, **kwargs)
        else:
            return IntegrationError.from_exception(
                exception,
                message=message,
                context=context,
                **kwargs
            )
    
    @staticmethod
    def log_error(error: IntegrationError, additional_context: Dict[str, Any] = None):
        """Log error with additional context."""
        error_data = error.to_dict()
        
        if additional_context:
            error_data['additional_context'] = additional_context
        
        logger.error(f"Integration Error: {error.message}", extra=error_data)
    
    @staticmethod
    def get_error_suggestions(error_code: str) -> List[str]:
        """Get suggestions for error code."""
        suggestions_map = {
            'NETWORK_ERROR': [
                "Check network connectivity",
                "Verify target service availability",
                "Check firewall settings"
            ],
            'AUTHENTICATION_ERROR': [
                "Check authentication credentials",
                "Verify API key validity",
                "Check token expiration"
            ],
            'VALIDATION_ERROR': [
                "Check data format",
                "Verify required fields",
                "Review validation rules"
            ],
            'TIMEOUT_ERROR': [
                "Increase timeout value",
                "Check network latency",
                "Optimize request processing"
            ],
            'RATE_LIMIT_ERROR': [
                "Reduce request frequency",
                "Implement exponential backoff",
                "Check rate limit quotas"
            ]
        }
        
        return suggestions_map.get(error_code, ["Contact support for assistance"])
    
    @staticmethod
    def is_retryable_error(error: IntegrationError) -> bool:
        """Check if error is retryable."""
        retryable_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.CIRCUIT_BREAKER
        ]
        
        return error.category in retryable_categories
    
    @staticmethod
    def get_retry_delay(error: IntegrationError, attempt: int = 1) -> int:
        """Get retry delay in seconds."""
        base_delay = 1
        
        if error.category == ErrorCategory.RATE_LIMIT:
            return error.retry_after or 60
        elif error.category == ErrorCategory.TIMEOUT:
            return min(base_delay * (2 ** attempt), 300)  # Max 5 minutes
        elif error.category == ErrorCategory.CIRCUIT_BREAKER:
            return error.retry_after or 60
        elif error.category == ErrorCategory.NETWORK:
            return min(base_delay * (2 ** attempt), 60)  # Max 1 minute
        else:
            return base_delay


# Error handler decorator
def handle_integration_errors(component: str, operation: str, 
                              default_error_type: type = IntegrationError):
    """Decorator for handling integration errors."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrationError as e:
                # Re-raise integration errors
                raise
            except Exception as e:
                # Wrap other exceptions
                raise ErrorUtils.wrap_exception(
                    e, component, operation,
                    default_error_type=default_error_type
                )
        return wrapper
    return decorator


# Error context manager
class ErrorContext:
    """Context manager for error handling."""
    
    def __init__(self, component: str, operation: str, **kwargs):
        self.component = component
        self.operation = operation
        self.context = ErrorUtils.create_error_context(component, operation, **kwargs)
    
    def __enter__(self):
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, Exception):
            if not issubclass(exc_type, IntegrationError):
                # Wrap non-integration errors
                raise ErrorUtils.wrap_exception(
                    exc_val, self.component, self.operation,
                    context=self.context
                )
        return False  # Don't suppress exceptions

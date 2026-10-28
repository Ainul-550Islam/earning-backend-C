"""
Integration Exceptions for alerts app - Custom exceptions for integration system
"""
from typing import Dict, Any, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class IntegrationException(Exception):
    """Base exception for all integration-related errors"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None, 
                 integration_name: str = None, timestamp: Any = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'INTEGRATION_ERROR'
        self.details = details or {}
        self.integration_name = integration_name
        self.timestamp = timestamp or timezone.now()
        self.severity = 'error'
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity,
            'integration_name': self.integration_name,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"
    
    def log(self):
        """Log the exception"""
        logger.error(
            f"Integration Exception: {self.to_dict()}",
            extra={
                'exception_type': self.__class__.__name__,
                'integration_name': self.integration_name,
                'error_code': self.error_code
            }
        )


class ConnectionException(IntegrationException):
    """Exception raised when connection to external system fails"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 connection_url: str = None, timeout: int = None, 
                 retry_count: int = None, **kwargs):
        super().__init__(
            message=message,
            error_code='CONNECTION_ERROR',
            integration_name=integration_name,
            details={
                'connection_url': connection_url,
                'timeout': timeout,
                'retry_count': retry_count,
                **kwargs
            }
        )
        self.connection_url = connection_url
        self.timeout = timeout
        self.retry_count = retry_count


class AuthenticationException(IntegrationException):
    """Exception raised when authentication fails"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 auth_type: str = None, username: str = None, 
                 **kwargs):
        super().__init__(
            message=message,
            error_code='AUTHENTICATION_ERROR',
            integration_name=integration_name,
            details={
                'auth_type': auth_type,
                'username': username,
                **kwargs
            }
        )
        self.auth_type = auth_type
        self.username = username


class AuthorizationException(IntegrationException):
    """Exception raised when authorization fails"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 required_permissions: list = None, user_permissions: list = None, 
                 **kwargs):
        super().__init__(
            message=message,
            error_code='AUTHORIZATION_ERROR',
            integration_name=integration_name,
            details={
                'required_permissions': required_permissions or [],
                'user_permissions': user_permissions or [],
                **kwargs
            }
        )
        self.required_permissions = required_permissions or []
        self.user_permissions = user_permissions or []


class ValidationException(IntegrationException):
    """Exception raised when data validation fails"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 field_name: str = None, field_value: Any = None, 
                 validation_rule: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code='VALIDATION_ERROR',
            integration_name=integration_name,
            details={
                'field_name': field_name,
                'field_value': field_value,
                'validation_rule': validation_rule,
                **kwargs
            }
        )
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule


class TimeoutException(IntegrationException):
    """Exception raised when operation times out"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 timeout_duration: int = None, operation: str = None, 
                 **kwargs):
        super().__init__(
            message=message,
            error_code='TIMEOUT_ERROR',
            integration_name=integration_name,
            details={
                'timeout_duration': timeout_duration,
                'operation': operation,
                **kwargs
            }
        )
        self.timeout_duration = timeout_duration
        self.operation = operation


class RateLimitException(IntegrationException):
    """Exception raised when rate limit is exceeded"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 rate_limit: int = None, current_usage: int = None, 
                 reset_time: Any = None, **kwargs):
        super().__init__(
            message=message,
            error_code='RATE_LIMIT_ERROR',
            integration_name=integration_name,
            details={
                'rate_limit': rate_limit,
                'current_usage': current_usage,
                'reset_time': reset_time.isoformat() if reset_time else None,
                **kwargs
            }
        )
        self.rate_limit = rate_limit
        self.current_usage = current_usage
        self.reset_time = reset_time


class ConfigurationException(IntegrationException):
    """Exception raised when configuration is invalid"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 config_key: str = None, config_value: Any = None, 
                 expected_type: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code='CONFIGURATION_ERROR',
            integration_name=integration_name,
            details={
                'config_key': config_key,
                'config_value': config_value,
                'expected_type': expected_type,
                **kwargs
            }
        )
        self.config_key = config_key
        self.config_value = config_value
        self.expected_type = expected_type


class DataFormatException(IntegrationException):
    """Exception raised when data format is invalid"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 expected_format: str = None, actual_format: str = None, 
                 data_sample: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code='DATA_FORMAT_ERROR',
            integration_name=integration_name,
            details={
                'expected_format': expected_format,
                'actual_format': actual_format,
                'data_sample': data_sample,
                **kwargs
            }
        )
        self.expected_format = expected_format
        self.actual_format = actual_format
        self.data_sample = data_sample


class ProtocolException(IntegrationException):
    """Exception raised when protocol-level error occurs"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 protocol: str = None, http_status: int = None, 
                 response_body: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code='PROTOCOL_ERROR',
            integration_name=integration_name,
            details={
                'protocol': protocol,
                'http_status': http_status,
                'response_body': response_body,
                **kwargs
            }
        )
        self.protocol = protocol
        self.http_status = http_status
        self.response_body = response_body


class ResourceUnavailableException(IntegrationException):
    """Exception raised when external resource is unavailable"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 resource_type: str = None, resource_url: str = None, 
                 retry_after: Any = None, **kwargs):
        super().__init__(
            message=message,
            error_code='RESOURCE_UNAVAILABLE',
            integration_name=integration_name,
            details={
                'resource_type': resource_type,
                'resource_url': resource_url,
                'retry_after': retry_after.isoformat() if retry_after else None,
                **kwargs
            }
        )
        self.resource_type = resource_type
        self.resource_url = resource_url
        self.retry_after = retry_after


class CircuitBreakerException(IntegrationException):
    """Exception raised when circuit breaker is open"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 failure_count: int = None, recovery_time: Any = None, 
                 **kwargs):
        super().__init__(
            message=message,
            error_code='CIRCUIT_BREAKER_OPEN',
            integration_name=integration_name,
            details={
                'failure_count': failure_count,
                'recovery_time': recovery_time.isoformat() if recovery_time else None,
                **kwargs
            }
        )
        self.failure_count = failure_count
        self.recovery_time = recovery_time


class TransformationException(IntegrationException):
    """Exception raised when data transformation fails"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 transformation_type: str = None, source_data: Any = None, 
                 target_format: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code='TRANSFORMATION_ERROR',
            integration_name=integration_name,
            details={
                'transformation_type': transformation_type,
                'source_data': str(source_data)[:500],  # Limit size
                'target_format': target_format,
                **kwargs
            }
        )
        self.transformation_type = transformation_type
        self.source_data = source_data
        self.target_format = target_format


class QueueException(IntegrationException):
    """Exception raised when queue operations fail"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 queue_name: str = None, operation: str = None, 
                 queue_size: int = None, **kwargs):
        super().__init__(
            message=message,
            error_code='QUEUE_ERROR',
            integration_name=integration_name,
            details={
                'queue_name': queue_name,
                'operation': operation,
                'queue_size': queue_size,
                **kwargs
            }
        )
        self.queue_name = queue_name
        self.operation = operation
        self.queue_size = queue_size


class WebhookException(IntegrationException):
    """Exception raised when webhook operations fail"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 webhook_url: str = None, event_type: str = None, 
                 signature_valid: bool = None, **kwargs):
        super().__init__(
            message=message,
            error_code='WEBHOOK_ERROR',
            integration_name=integration_name,
            details={
                'webhook_url': webhook_url,
                'event_type': event_type,
                'signature_valid': signature_valid,
                **kwargs
            }
        )
        self.webhook_url = webhook_url
        self.event_type = event_type
        self.signature_valid = signature_valid


class CriticalIntegrationException(IntegrationException):
    """Critical exception that should trigger immediate attention"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 impact_level: str = None, affected_systems: list = None, 
                 **kwargs):
        super().__init__(
            message=message,
            error_code='CRITICAL_INTEGRATION_ERROR',
            integration_name=integration_name,
            details={
                'impact_level': impact_level,
                'affected_systems': affected_systems or [],
                **kwargs
            }
        )
        self.severity = 'critical'
        self.impact_level = impact_level
        self.affected_systems = affected_systems or []


class IntegrationWarning(UserWarning):
    """Warning for integration issues that don't require immediate action"""
    
    def __init__(self, message: str, integration_name: str = None, 
                 warning_type: str = None, **kwargs):
        super().__init__(message)
        self.integration_name = integration_name
        self.warning_type = warning_type
        self.details = kwargs


class IntegrationErrorLogger:
    """Utility class for logging integration errors"""
    
    def __init__(self, integration_name: str):
        self.integration_name = integration_name
        self.error_counts = {}
        self.last_errors = []
        self.max_errors = 1000
        
    def log_exception(self, exception: IntegrationException):
        """Log integration exception with context"""
        exception.log()
        
        # Update error counts
        error_type = exception.__class__.__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Update last errors
        error_record = {
            'timestamp': exception.timestamp.isoformat(),
            'error_type': error_type,
            'error_code': exception.error_code,
            'message': exception.message,
            'details': exception.details
        }
        
        self.last_errors.append(error_record)
        
        # Keep only recent errors
        if len(self.last_errors) > self.max_errors:
            self.last_errors = self.last_errors[-self.max_errors:]
        
        # Log to external monitoring if critical
        if isinstance(exception, CriticalIntegrationException):
            self._log_to_external_monitoring(exception)
    
    def _log_to_external_monitoring(self, exception: CriticalIntegrationException):
        """Log critical exceptions to external monitoring systems"""
        try:
            # This would integrate with systems like Sentry, DataDog, etc.
            # For now, just log with higher severity
            logger.critical(
                f"CRITICAL Integration Error: {exception.to_dict()}",
                extra={
                    'integration_name': self.integration_name,
                    'impact_level': exception.impact_level,
                    'affected_systems': exception.affected_systems
                }
            )
        except Exception as e:
            logger.error(f"Error logging to external monitoring: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            'integration_name': self.integration_name,
            'error_counts': self.error_counts.copy(),
            'total_errors': sum(self.error_counts.values()),
            'recent_errors': self.last_errors[-10:],  # Last 10 errors
            'last_updated': timezone.now().isoformat()
        }
    
    def get_error_rate(self, time_window_minutes: int = 60) -> float:
        """Calculate error rate in specified time window"""
        cutoff_time = timezone.now() - timezone.timedelta(minutes=time_window_minutes)
        
        recent_errors = [
            error for error in self.last_errors
            if timezone.datetime.fromisoformat(error['timestamp']) > cutoff_time
        ]
        
        return len(recent_errors) / time_window_minutes if time_window_minutes > 0 else 0
    
    def clear_error_history(self):
        """Clear error history"""
        self.error_counts.clear()
        self.last_errors.clear()
        logger.info(f"Cleared error history for integration: {self.integration_name}")


class ExceptionHandler:
    """Handler for processing and managing integration exceptions"""
    
    def __init__(self):
        self.handlers = {}
        self.error_logger = None
        
    def register_handler(self, exception_type: type, handler: callable):
        """Register handler for specific exception type"""
        self.handlers[exception_type] = handler
        logger.info(f"Registered exception handler for {exception_type.__name__}")
    
    def handle_exception(self, exception: IntegrationException, context: Dict[str, Any] = None):
        """Handle integration exception"""
        exception_type = type(exception)
        
        # Log the exception
        if not self.error_logger:
            self.error_logger = IntegrationErrorLogger(
                context.get('integration_name', 'unknown') if context else 'unknown'
            )
        
        self.error_logger.log_exception(exception)
        
        # Get handler for this exception type
        handler = self.handlers.get(exception_type)
        
        if handler:
            try:
                return handler(exception, context)
            except Exception as e:
                logger.error(f"Error in exception handler: {e}")
        
        # Default handling
        return self._default_exception_handling(exception, context)
    
    def _default_exception_handling(self, exception: IntegrationException, context: Dict[str, Any] = None):
        """Default exception handling logic"""
        # Determine retry eligibility
        should_retry = self._should_retry_exception(exception)
        
        # Determine escalation level
        escalation_level = self._determine_escalation_level(exception)
        
        return {
            'handled': True,
            'should_retry': should_retry,
            'escalation_level': escalation_level,
            'retry_delay': self._calculate_retry_delay(exception),
            'context': context or {}
        }
    
    def _should_retry_exception(self, exception: IntegrationException) -> bool:
        """Determine if exception should trigger a retry"""
        # Don't retry critical errors
        if isinstance(exception, CriticalIntegrationException):
            return False
        
        # Don't retry authentication errors
        if isinstance(exception, AuthenticationException):
            return False
        
        # Don't retry authorization errors
        if isinstance(exception, AuthorizationException):
            return False
        
        # Retry connection errors, timeouts, and rate limit errors
        if isinstance(exception, (ConnectionException, TimeoutException, RateLimitException)):
            return True
        
        # Retry validation errors with caution
        if isinstance(exception, ValidationException):
            return False  # Usually user input errors
        
        return False
    
    def _determine_escalation_level(self, exception: IntegrationException) -> str:
        """Determine escalation level for exception"""
        if isinstance(exception, CriticalIntegrationException):
            return 'critical'
        elif isinstance(exception, (ConnectionException, CircuitBreakerException)):
            return 'high'
        elif isinstance(exception, (TimeoutException, ResourceUnavailableException)):
            return 'medium'
        else:
            return 'low'
    
    def _calculate_retry_delay(self, exception: IntegrationException) -> int:
        """Calculate retry delay based on exception type"""
        base_delay = 60  # 1 minute base
        
        if isinstance(exception, RateLimitException):
            # Use reset time from rate limit exception
            if exception.reset_time:
                time_until_reset = exception.reset_time - timezone.now()
                return max(0, int(time_until_reset.total_seconds()))
        
        elif isinstance(exception, ResourceUnavailableException):
            # Use retry_after from resource exception
            if exception.retry_after:
                time_until_retry = exception.retry_after - timezone.now()
                return max(0, int(time_until_retry.total_seconds()))
        
        elif isinstance(exception, ConnectionException):
            # Exponential backoff for connection errors
            retry_count = getattr(exception, 'retry_count', 1)
            return base_delay * (2 ** (retry_count - 1))
        
        else:
            return base_delay


# Utility functions
def create_connection_error(message: str, integration_name: str = None, **kwargs) -> ConnectionException:
    """Create connection error with standard message"""
    return ConnectionException(
        message=message,
        integration_name=integration_name,
        **kwargs
    )


def create_authentication_error(message: str, integration_name: str = None, **kwargs) -> AuthenticationException:
    """Create authentication error with standard message"""
    return AuthenticationException(
        message=message,
        integration_name=integration_name,
        **kwargs
    )


def create_validation_error(field_name: str, field_value: Any = None, **kwargs) -> ValidationException:
    """Create validation error with standard message"""
    message = kwargs.get('message', f"Validation failed for field: {field_name}")
    
    return ValidationException(
        message=message,
        field_name=field_name,
        field_value=field_value,
        **kwargs
    )


def create_timeout_error(operation: str, timeout_duration: int = None, **kwargs) -> TimeoutException:
    """Create timeout error with standard message"""
    message = kwargs.get('message', f"Operation '{operation}' timed out")
    
    return TimeoutException(
        message=message,
        operation=operation,
        timeout_duration=timeout_duration,
        **kwargs
    )


def create_rate_limit_error(rate_limit: int, current_usage: int = None, **kwargs) -> RateLimitException:
    """Create rate limit error with standard message"""
    message = kwargs.get('message', f"Rate limit exceeded: {current_usage}/{rate_limit}")
    
    return RateLimitException(
        message=message,
        rate_limit=rate_limit,
        current_usage=current_usage,
        **kwargs
    )


def create_circuit_breaker_error(failure_count: int = None, **kwargs) -> CircuitBreakerException:
    """Create circuit breaker error with standard message"""
    message = kwargs.get('message', "Circuit breaker is open")
    
    return CircuitBreakerException(
        message=message,
        failure_count=failure_count,
        **kwargs
    )


def handle_integration_exception(func):
    """Decorator for handling integration exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrationException as e:
            handler = ExceptionHandler()
            result = handler.handle_exception(e, kwargs)
            
            # Re-raise if not handled
            if not result.get('handled', False):
                raise e
            
            return result
        except Exception as e:
            # Wrap non-integration exceptions
            integration_exception = IntegrationException(
                message=f"Unexpected error: {str(e)}",
                error_code='UNEXPECTED_ERROR',
                details={'original_exception': str(e)}
            )
            
            handler = ExceptionHandler()
            result = handler.handle_exception(integration_exception, kwargs)
            
            if not result.get('handled', False):
                raise integration_exception
            
            return result
    
    return wrapper


# Global exception handler
global_exception_handler = ExceptionHandler()

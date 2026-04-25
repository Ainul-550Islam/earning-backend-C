"""Integration Exceptions

This module provides custom exceptions for integration system
with comprehensive error handling and error reporting.
"""

import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration system."""
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        """Initialize integration error."""
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'INTEGRATION_ERROR'
        self.context = context or {}
        self.timestamp = timezone.now()
        self.stack_trace = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'stack_trace': self.stack_trace
        }


class HandlerError(IntegrationError):
    """Exception for handler errors."""
    
    def __init__(self, message: str, handler_name: str = None, context: Dict[str, Any] = None):
        """Initialize handler error."""
        super().__init__(message, 'HANDLER_ERROR', context)
        self.handler_name = handler_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['handler_name'] = self.handler_name
        return result


class AdapterError(IntegrationError):
    """Exception for adapter errors."""
    
    def __init__(self, message: str, adapter_type: str = None, context: Dict[str, Any] = None):
        """Initialize adapter error."""
        super().__init__(message, 'ADAPTER_ERROR', context)
        self.adapter_type = adapter_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['adapter_type'] = self.adapter_type
        return result


class RegistryError(IntegrationError):
    """Exception for registry errors."""
    
    def __init__(self, message: str, registry_type: str = None, context: Dict[str, Any] = None):
        """Initialize registry error."""
        super().__init__(message, 'REGISTRY_ERROR', context)
        self.registry_type = registry_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['registry_type'] = self.registry_type
        return result


class SignalError(IntegrationError):
    """Exception for signal errors."""
    
    def __init__(self, message: str, signal_type: str = None, context: Dict[str, Any] = None):
        """Initialize signal error."""
        super().__init__(message, 'SIGNAL_ERROR', context)
        self.signal_type = signal_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['signal_type'] = self.signal_type
        return result


class BridgeError(IntegrationError):
    """Exception for bridge errors."""
    
    def __init__(self, message: str, bridge_type: str = None, context: Dict[str, Any] = None):
        """Initialize bridge error."""
        super().__init__(message, 'BRIDGE_ERROR', context)
        self.bridge_type = bridge_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['bridge_type'] = self.bridge_type
        return result


class EventBusError(IntegrationError):
    """Exception for event bus errors."""
    
    def __init__(self, message: str, event_type: str = None, context: Dict[str, Any] = None):
        """Initialize event bus error."""
        super().__init__(message, 'EVENT_BUS_ERROR', context)
        self.event_type = event_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['event_type'] = self.event_type
        return result


class QueueError(IntegrationError):
    """Exception for queue errors."""
    
    def __init__(self, message: str, queue_name: str = None, context: Dict[str, Any] = None):
        """Initialize queue error."""
        super().__init__(message, 'QUEUE_ERROR', context)
        self.queue_name = queue_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['queue_name'] = self.queue_name
        return result


class ValidationError(IntegrationError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, validation_type: str = None, field: str = None, context: Dict[str, Any] = None):
        """Initialize validation error."""
        super().__init__(message, 'VALIDATION_ERROR', context)
        self.validation_type = validation_type
        self.field = field
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['validation_type'] = self.validation_type
        result['field'] = self.field
        return result


class TransformationError(IntegrationError):
    """Exception for transformation errors."""
    
    def __init__(self, message: str, transformation_name: str = None, context: Dict[str, Any] = None):
        """Initialize transformation error."""
        super().__init__(message, 'TRANSFORMATION_ERROR', context)
        self.transformation_name = transformation_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['transformation_name'] = self.transformation_name
        return result


class AuthError(IntegrationError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str, auth_type: str = None, context: Dict[str, Any] = None):
        """Initialize auth error."""
        super().__init__(message, 'AUTH_ERROR', context)
        self.auth_type = auth_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['auth_type'] = self.auth_type
        return result


class SyncError(IntegrationError):
    """Exception for synchronization errors."""
    
    def __init__(self, message: str, sync_type: str = None, context: Dict[str, Any] = None):
        """Initialize sync error."""
        super().__init__(message, 'SYNC_ERROR', context)
        self.sync_type = sync_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['sync_type'] = self.sync_type
        return result


class TimeoutError(IntegrationError):
    """Exception for timeout errors."""
    
    def __init__(self, message: str, timeout_seconds: int = None, context: Dict[str, Any] = None):
        """Initialize timeout error."""
        super().__init__(message, 'TIMEOUT_ERROR', context)
        self.timeout_seconds = timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['timeout_seconds'] = self.timeout_seconds
        return result


class ConfigurationError(IntegrationError):
    """Exception for configuration errors."""
    
    def __init__(self, message: str, config_key: str = None, context: Dict[str, Any] = None):
        """Initialize configuration error."""
        super().__init__(message, 'CONFIGURATION_ERROR', context)
        self.config_key = config_key
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['config_key'] = self.config_key
        return result


class ConnectionError(IntegrationError):
    """Exception for connection errors."""
    
    def __init__(self, message: str, connection_type: str = None, context: Dict[str, Any] = None):
        """Initialize connection error."""
        super().__init__(message, 'CONNECTION_ERROR', context)
        self.connection_type = connection_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['connection_type'] = self.connection_type
        return result


class RateLimitError(IntegrationError):
    """Exception for rate limit errors."""
    
    def __init__(self, message: str, limit_type: str = None, context: Dict[str, Any] = None):
        """Initialize rate limit error."""
        super().__init__(message, 'RATE_LIMIT_ERROR', context)
        self.limit_type = limit_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['limit_type'] = self.limit_type
        return result


class CircuitBreakerError(IntegrationError):
    """Exception for circuit breaker errors."""
    
    def __init__(self, message: str, service_name: str = None, context: Dict[str, Any] = None):
        """Initialize circuit breaker error."""
        super().__init__(message, 'CIRCUIT_BREAKER_ERROR', context)
        self.service_name = service_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['service_name'] = self.service_name
        return result


class RetryExhaustedError(IntegrationError):
    """Exception for retry exhausted errors."""
    
    def __init__(self, message: str, retry_count: int = None, context: Dict[str, Any] = None):
        """Initialize retry exhausted error."""
        super().__init__(message, 'RETRY_EXHAUSTED_ERROR', context)
        self.retry_count = retry_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['retry_count'] = self.retry_count
        return result


class DeadLetterError(IntegrationError):
    """Exception for dead letter errors."""
    
    def __init__(self, message: str, queue_name: str = None, context: Dict[str, Any] = None):
        """Initialize dead letter error."""
        super().__init__(message, 'DEAD_LETTER_ERROR', context)
        self.queue_name = queue_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        result = super().to_dict()
        result['queue_name'] = self.queue_name
        return result


class ExceptionHandler:
    """Exception handler for integration system."""
    
    def __init__(self):
        """Initialize the exception handler."""
        self.logger = logger
        self.error_history = []
        self.max_history = 1000
    
    def handle_exception(self, exception: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle an exception and return error information.
        
        Args:
            exception: The exception to handle
            context: Additional context
            
        Returns:
            Error information
        """
        try:
            # Convert to integration error if not already
            if not isinstance(exception, IntegrationError):
                integration_error = IntegrationError(
                    str(exception),
                    context=context
                )
            else:
                integration_error = exception
            
            # Add stack trace
            import traceback
            integration_error.stack_trace = traceback.format_exc()
            
            # Add to history
            self._add_to_history(integration_error)
            
            # Log error
            self._log_error(integration_error)
            
            # Return error information
            return integration_error.to_dict()
            
        except Exception as e:
            # Fallback error handling
            self.logger.error(f"Error in exception handler: {str(e)}")
            return {
                'error_type': 'INTERNAL_ERROR',
                'error_code': 'EXCEPTION_HANDLER_ERROR',
                'message': str(e),
                'timestamp': timezone.now().isoformat(),
                'stack_trace': traceback.format_exc()
            }
    
    def _add_to_history(self, error: IntegrationError):
        """Add error to history."""
        try:
            self.error_history.append(error.to_dict())
            
            # Limit history size
            if len(self.error_history) > self.max_history:
                self.error_history = self.error_history[-self.max_history:]
                
        except Exception as e:
            self.logger.error(f"Error adding to history: {str(e)}")
    
    def _log_error(self, error: IntegrationError):
        """Log error with appropriate level."""
        try:
            log_message = f"[{error.error_code}] {error.message}"
            
            if error.context:
                log_message += f" | Context: {error.context}"
            
            if error.error_code in ['CRITICAL_ERROR', 'SYSTEM_ERROR']:
                self.logger.critical(log_message)
            elif error.error_code in ['TIMEOUT_ERROR', 'CONNECTION_ERROR']:
                self.logger.error(log_message)
            else:
                self.logger.warning(log_message)
                
        except Exception as e:
            self.logger.error(f"Error logging error: {str(e)}")
    
    def get_error_history(self, error_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get error history.
        
        Args:
            error_type: Optional error type filter
            limit: Maximum number of entries to return
            
        Returns:
            Error history
        """
        try:
            history = self.error_history
            
            # Filter by error type
            if error_type:
                history = [
                    error for error in history
                    if error.get('error_type') == error_type
                ]
            
            # Limit results
            if limit:
                history = history[-limit:]
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting error history: {str(e)}")
            return []
    
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Error statistics
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(hours=hours)
            
            # Filter recent errors
            recent_errors = [
                error for error in self.error_history
                if timezone.parse(error['timestamp']) >= since
            ]
            
            # Calculate statistics
            total_errors = len(recent_errors)
            error_types = {}
            error_codes = {}
            
            for error in recent_errors:
                error_type = error.get('error_type', 'Unknown')
                error_code = error.get('error_code', 'Unknown')
                
                error_types[error_type] = error_types.get(error_type, 0) + 1
                error_codes[error_code] = error_codes.get(error_code, 0) + 1
            
            return {
                'period_hours': hours,
                'total_errors': total_errors,
                'error_types': error_types,
                'error_codes': error_codes,
                'most_common_error_type': max(error_types, key=error_types.get) if error_types else None,
                'most_common_error_code': max(error_codes, key=error_codes.get) if error_codes else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting error statistics: {str(e)}")
            return {
                'period_hours': hours,
                'total_errors': 0,
                'error_types': {},
                'error_codes': {},
                'error': str(e)
            }
    
    def clear_history(self) -> bool:
        """
        Clear error history.
        
        Returns:
            True if clear successful
        """
        try:
            self.error_history.clear()
            self.logger.info("Error history cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing history: {str(e)}")
            return False


# Global exception handler instance
exception_handler = ExceptionHandler()

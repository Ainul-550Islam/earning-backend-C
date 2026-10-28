from typing import Type, Callable, Any, Dict, List, Optional
"""
Integration Exceptions Module
Custom exceptions for integration system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger('security.integration.exceptions')


class IntegrationException(Exception):
    """Base integration exception"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'INTEGRATION_ERROR'
        self.details = details or {}
        self.timestamp = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class ConnectionException(IntegrationException):
    """Connection related exception"""
    
    def __init__(self, message: str, endpoint: str = None, status_code: int = None, 
                 response_text: str = None):
        super().__init__(message, 'CONNECTION_ERROR')
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_text = response_text
        
        if endpoint:
            self.details['endpoint'] = endpoint
        if status_code:
            self.details['status_code'] = status_code
        if response_text:
            self.details['response_text'] = response_text


class AuthenticationException(IntegrationException):
    """Authentication related exception"""
    
    def __init__(self, message: str, auth_type: str = None, username: str = None):
        super().__init__(message, 'AUTHENTICATION_ERROR')
        self.auth_type = auth_type
        self.username = username
        
        if auth_type:
            self.details['auth_type'] = auth_type
        if username:
            self.details['username'] = username


class ValidationException(IntegrationException):
    """Validation related exception"""
    
    def __init__(self, message: str, field: str = None, value: Any = None, 
                 validation_rule: str = None):
        super().__init__(message, 'VALIDATION_ERROR')
        self.field = field
        self.value = value
        self.validation_rule = validation_rule
        
        if field:
            self.details['field'] = field
        if value is not None:
            self.details['value'] = str(value)
        if validation_rule:
            self.details['validation_rule'] = validation_rule


class TransformationException(IntegrationException):
    """Data transformation exception"""
    
    def __init__(self, message: str, source_format: str = None, target_format: str = None, 
                 transformer_name: str = None):
        super().__init__(message, 'TRANSFORMATION_ERROR')
        self.source_format = source_format
        self.target_format = target_format
        self.transformer_name = transformer_name
        
        if source_format:
            self.details['source_format'] = source_format
        if target_format:
            self.details['target_format'] = target_format
        if transformer_name:
            self.details['transformer_name'] = transformer_name


class SerializationException(IntegrationException):
    """Serialization exception"""
    
    def __init__(self, message: str, data_type: str = None, format_type: str = None):
        super().__init__(message, 'SERIALIZATION_ERROR')
        self.data_type = data_type
        self.format_type = format_type
        
        if data_type:
            self.details['data_type'] = data_type
        if format_type:
            self.details['format_type'] = format_type


class DeserializationException(IntegrationException):
    """Deserialization exception"""
    
    def __init__(self, message: str, data_type: str = None, format_type: str = None):
        super().__init__(message, 'DESERIALIZATION_ERROR')
        self.data_type = data_type
        self.format_type = format_type
        
        if data_type:
            self.details['data_type'] = data_type
        if format_type:
            self.details['format_type'] = format_type


class RateLimitException(IntegrationException):
    """Rate limit exception"""
    
    def __init__(self, message: str, limit: int = None, window: int = None, 
                 retry_after: int = None):
        super().__init__(message, 'RATE_LIMIT_ERROR')
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        
        if limit:
            self.details['limit'] = limit
        if window:
            self.details['window'] = window
        if retry_after:
            self.details['retry_after'] = retry_after


class TimeoutException(IntegrationException):
    """Timeout exception"""
    
    def __init__(self, message: str, timeout_seconds: int = None, operation: str = None):
        super().__init__(message, 'TIMEOUT_ERROR')
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        
        if timeout_seconds:
            self.details['timeout_seconds'] = timeout_seconds
        if operation:
            self.details['operation'] = operation


class CircuitBreakerOpenException(IntegrationException):
    """Circuit breaker open exception"""
    
    def __init__(self, message: str, circuit_name: str = None, failure_count: int = None):
        super().__init__(message, 'CIRCUIT_BREAKER_OPEN')
        self.circuit_name = circuit_name
        self.failure_count = failure_count
        
        if circuit_name:
            self.details['circuit_name'] = circuit_name
        if failure_count:
            self.details['failure_count'] = failure_count


class ConfigurationException(IntegrationException):
    """Configuration exception"""
    
    def __init__(self, message: str, config_key: str = None, config_value: Any = None):
        super().__init__(message, 'CONFIGURATION_ERROR')
        self.config_key = config_key
        self.config_value = config_value
        
        if config_key:
            self.details['config_key'] = config_key
        if config_value is not None:
            self.details['config_value'] = str(config_value)


class DependencyException(IntegrationException):
    """Dependency exception"""
    
    def __init__(self, message: str, dependency_name: str = None, required_version: str = None):
        super().__init__(message, 'DEPENDENCY_ERROR')
        self.dependency_name = dependency_name
        self.required_version = required_version
        
        if dependency_name:
            self.details['dependency_name'] = dependency_name
        if required_version:
            self.details['required_version'] = required_version


class VersionException(IntegrationException):
    """Version compatibility exception"""
    
    def __init__(self, message: str, current_version: str = None, 
                 required_version: str = None):
        super().__init__(message, 'VERSION_ERROR')
        self.current_version = current_version
        self.required_version = required_version
        
        if current_version:
            self.details['current_version'] = current_version
        if required_version:
            self.details['required_version'] = required_version


class QueueException(IntegrationException):
    """Queue related exception"""
    
    def __init__(self, message: str, queue_name: str = None, queue_size: int = None):
        super().__init__(message, 'QUEUE_ERROR')
        self.queue_name = queue_name
        self.queue_size = queue_size
        
        if queue_name:
            self.details['queue_name'] = queue_name
        if queue_size:
            self.details['queue_size'] = queue_size


class MessageException(IntegrationException):
    """Message related exception"""
    
    def __init__(self, message: str, message_id: str = None, message_type: str = None):
        super().__init__(message, 'MESSAGE_ERROR')
        self.message_id = message_id
        self.message_type = message_type
        
        if message_id:
            self.details['message_id'] = message_id
        if message_type:
            self.details['message_type'] = message_type


class WebhookException(IntegrationException):
    """Webhook related exception"""
    
    def __init__(self, message: str, webhook_url: str = None, webhook_name: str = None):
        super().__init__(message, 'WEBHOOK_ERROR')
        self.webhook_url = webhook_url
        self.webhook_name = webhook_name
        
        if webhook_url:
            self.details['webhook_url'] = webhook_url
        if webhook_name:
            self.details['webhook_name'] = webhook_name


class DataSyncException(IntegrationException):
    """Data synchronization exception"""
    
    def __init__(self, message: str, source_system: str = None, target_system: str = None, 
                 sync_rule: str = None):
        super().__init__(message, 'DATA_SYNC_ERROR')
        self.source_system = source_system
        self.target_system = target_system
        self.sync_rule = sync_rule
        
        if source_system:
            self.details['source_system'] = source_system
        if target_system:
            self.details['target_system'] = target_system
        if sync_rule:
            self.details['sync_rule'] = sync_rule


class ConflictException(IntegrationException):
    """Data conflict exception"""
    
    def __init__(self, message: str, conflict_type: str = None, conflict_field: str = None, 
                 source_value: Any = None, target_value: Any = None):
        super().__init__(message, 'CONFLICT_ERROR')
        self.conflict_type = conflict_type
        self.conflict_field = conflict_field
        self.source_value = source_value
        self.target_value = target_value
        
        if conflict_type:
            self.details['conflict_type'] = conflict_type
        if conflict_field:
            self.details['conflict_field'] = conflict_field
        if source_value is not None:
            self.details['source_value'] = str(source_value)
        if target_value is not None:
            self.details['target_value'] = str(target_value)


class PermissionException(IntegrationException):
    """Permission exception"""
    
    def __init__(self, message: str, required_permission: str = None, user_id: str = None):
        super().__init__(message, 'PERMISSION_ERROR')
        self.required_permission = required_permission
        self.user_id = user_id
        
        if required_permission:
            self.details['required_permission'] = required_permission
        if user_id:
            self.details['user_id'] = user_id


class ResourceException(IntegrationException):
    """Resource related exception"""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        super().__init__(message, 'RESOURCE_ERROR')
        self.resource_type = resource_type
        self.resource_id = resource_id
        
        if resource_type:
            self.details['resource_type'] = resource_type
        if resource_id:
            self.details['resource_id'] = resource_id


class RetryException(IntegrationException):
    """Retry exception"""
    
    def __init__(self, message: str, attempt: int = None, max_attempts: int = None, 
                 next_retry: datetime = None):
        super().__init__(message, 'RETRY_ERROR')
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.next_retry = next_retry
        
        if attempt:
            self.details['attempt'] = attempt
        if max_attempts:
            self.details['max_attempts'] = max_attempts
        if next_retry:
            self.details['next_retry'] = next_retry.isoformat()


class HealthCheckException(IntegrationException):
    """Health check exception"""
    
    def __init__(self, message: str, component_name: str = None, health_status: str = None):
        super().__init__(message, 'HEALTH_CHECK_ERROR')
        self.component_name = component_name
        self.health_status = health_status
        
        if component_name:
            self.details['component_name'] = component_name
        if health_status:
            self.details['health_status'] = health_status


class MonitoringException(IntegrationException):
    """Monitoring exception"""
    
    def __init__(self, message: str, metric_name: str = None, metric_value: Any = None):
        super().__init__(message, 'MONITORING_ERROR')
        self.metric_name = metric_name
        self.metric_value = metric_value
        
        if metric_name:
            self.details['metric_name'] = metric_name
        if metric_value is not None:
            self.details['metric_value'] = str(metric_value)


class CacheException(IntegrationException):
    """Cache exception"""
    
    def __init__(self, message: str, cache_key: str = None, cache_operation: str = None):
        super().__init__(message, 'CACHE_ERROR')
        self.cache_key = cache_key
        self.cache_operation = cache_operation
        
        if cache_key:
            self.details['cache_key'] = cache_key
        if cache_operation:
            self.details['cache_operation'] = cache_operation


class ExceptionHandler:
    """Handler for integration exceptions"""
    
    def __init__(self):
        self.exception_handlers = {}
        self.default_handler = self._default_handler
        self.enabled = True
    
    def register_handler(self, exception_type: Type[IntegrationException], handler: Callable):
        """Register exception handler"""
        self.exception_handlers[exception_type] = handler
        logger.info(f"Registered exception handler for: {exception_type.__name__}")
    
    def unregister_handler(self, exception_type: Type[IntegrationException]):
        """Unregister exception handler"""
        if exception_type in self.exception_handlers:
            del self.exception_handlers[exception_type]
            logger.info(f"Unregistered exception handler for: {exception_type.__name__}")
    
    def handle_exception(self, exception: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle exception"""
        if not self.enabled:
            return self._create_error_response(exception)
        
        try:
            # Find appropriate handler
            handler = None
            for exception_type, registered_handler in self.exception_handlers.items():
                if isinstance(exception, exception_type):
                    handler = registered_handler
                    break
            
            if handler:
                return handler(exception, context or {})
            else:
                return self.default_handler(exception, context or {})
        
        except Exception as e:
            logger.error(f"Error in exception handler: {e}")
            return self._create_error_response(exception)
    
    def _default_handler(self, exception: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default exception handler"""
        return {
            'status': 'error',
            'error_type': exception.__class__.__name__,
            'message': str(exception),
            'context': context,
            'timestamp': timezone.now().isoformat()
        }
    
    def _create_error_response(self, exception: Exception) -> Dict[str, Any]:
        """Create error response"""
        return {
            'status': 'error',
            'error_type': exception.__class__.__name__,
            'message': str(exception),
            'timestamp': timezone.now().isoformat()
        }
    
    def enable(self):
        """Enable exception handler"""
        self.enabled = True
        logger.info("Exception handler enabled")
    
    def disable(self):
        """Disable exception handler"""
        self.enabled = False
        logger.info("Exception handler disabled")


# Global exception handler
exception_handler = ExceptionHandler()


# Built-in exception handlers
def log_integration_exception(exception: IntegrationException, context: Dict[str, Any]) -> Dict[str, Any]:
    """Log integration exception"""
    logger.error(f"Integration exception: {exception.message}", extra={
        'error_code': exception.error_code,
        'details': exception.details,
        'context': context
    })
    
    return {
        'status': 'error',
        'error_code': exception.error_code,
        'message': exception.message,
        'details': exception.details,
        'context': context,
        'timestamp': exception.timestamp.isoformat()
    }


def handle_connection_exception(exception: ConnectionException, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle connection exception"""
    logger.warning(f"Connection error: {exception.message}", extra={
        'endpoint': exception.endpoint,
        'status_code': exception.status_code,
        'context': context
    })
    
    # Create security incident for repeated connection failures
    from ..models import SecurityIncident
    
    if exception.status_code and exception.status_code >= 500:
        SecurityIncident.objects.create(
            title=f"Integration Connection Error: {exception.endpoint}",
            incident_type='integration_failure',
            severity='medium',
            priority='medium',
            description=f"Connection failed to {exception.endpoint}: {exception.message}",
            metadata={
                'endpoint': exception.endpoint,
                'status_code': exception.status_code,
                'error_code': exception.error_code
            }
        )
    
    return {
        'status': 'error',
        'error_code': exception.error_code,
        'message': exception.message,
        'endpoint': exception.endpoint,
        'status_code': exception.status_code,
        'retry_suggested': True
    }


def handle_validation_exception(exception: ValidationException, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle validation exception"""
    logger.warning(f"Validation error: {exception.message}", extra={
        'field': exception.field,
        'validation_rule': exception.validation_rule,
        'context': context
    })
    
    return {
        'status': 'validation_error',
        'error_code': exception.error_code,
        'message': exception.message,
        'field': exception.field,
        'validation_rule': exception.validation_rule,
        'value': exception.value
    }


def handle_rate_limit_exception(exception: RateLimitException, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle rate limit exception"""
    logger.warning(f"Rate limit exceeded: {exception.message}", extra={
        'limit': exception.limit,
        'window': exception.window,
        'context': context
    })
    
    return {
        'status': 'rate_limited',
        'error_code': exception.error_code,
        'message': exception.message,
        'limit': exception.limit,
        'window': exception.window,
        'retry_after': exception.retry_after
    }


# Register built-in handlers
exception_handler.register_handler(ConnectionException, handle_connection_exception)
exception_handler.register_handler(ValidationException, handle_validation_exception)
exception_handler.register_handler(RateLimitException, handle_rate_limit_exception)
exception_handler.register_handler(IntegrationException, log_integration_exception)


# Export symbols
__all__ = [
    'IntegrationException',
    'ConnectionException',
    'AuthenticationException',
    'ValidationException',
    'TransformationException',
    'SerializationException',
    'DeserializationException',
    'RateLimitException',
    'TimeoutException',
    'CircuitBreakerOpenException',
    'ConfigurationException',
    'DependencyException',
    'VersionException',
    'QueueException',
    'MessageException',
    'WebhookException',
    'DataSyncException',
    'ConflictException',
    'PermissionException',
    'ResourceException',
    'RetryException',
    'HealthCheckException',
    'MonitoringException',
    'CacheException',
    'ExceptionHandler',
    'exception_handler',
    'log_integration_exception',
    'handle_connection_exception',
    'handle_validation_exception',
    'handle_rate_limit_exception'
]
"""
Integration Exceptions

Custom exceptions for integration system.
"""

from typing import Dict, Any, Optional
from django.utils import timezone
from .integ_constants import IntegrationType, IntegrationStatus

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration system."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.integration_id = integration_id
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = timezone.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            'error': self.message,
            'integration_id': self.integration_id,
            'error_code': self.error_code,
            'context': self.context,
            'timestamp': self.timestamp
        }


class IntegrationConfigurationError(IntegrationError):
    """Exception for integration configuration errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 config_field: str = None, config_value: Any = None):
        super().__init__(message, integration_id, 'E001')
        self.config_field = config_field
        self.config_value = config_value


class IntegrationConnectionError(IntegrationError):
    """Exception for integration connection errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 endpoint: str = None, status_code: int = None):
        super().__init__(message, integration_id, 'E002')
        self.endpoint = endpoint
        self.status_code = status_code


class IntegrationTimeoutError(IntegrationError):
    """Exception for integration timeout errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 timeout_seconds: int = None):
        super().__init__(message, integration_id, 'E003')
        self.timeout_seconds = timeout_seconds


class IntegrationAuthenticationError(IntegrationError):
    """Exception for integration authentication errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 auth_type: str = None):
        super().__init__(message, integration_id, 'E005')
        self.auth_type = auth_type


class IntegrationAuthorizationError(IntegrationError):
    """Exception for integration authorization errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 required_permission: str = None):
        super().__init__(message, integration_id, 'E006')
        self.required_permission = required_permission


class IntegrationValidationError(IntegrationError):
    """Exception for integration validation errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 validation_errors: Dict[str, Any] = None):
        super().__init__(message, integration_id, 'E010')
        self.validation_errors = validation_errors or {}


class IntegrationDataError(IntegrationError):
    """Exception for integration data errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 data_type: str = None, data_value: Any = None):
        super().__init__(message, integration_id, 'E008')
        self.data_type = data_type
        self.data_value = data_value


class IntegrationSyncError(IntegrationError):
    """Exception for integration synchronization errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 sync_type: str = None, sync_data: Any = None):
        super().__init__(message, integration_id, 'E011')
        self.sync_type = sync_type
        self.sync_data = sync_data


class IntegrationVersionError(IntegrationError):
    """Exception for integration version errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 current_version: str = None, required_version: str = None):
        super().__init__(message, integration_id, 'E012')
        self.current_version = current_version
        self.required_version = required_version


class IntegrationDependencyError(IntegrationError):
    """Exception for integration dependency errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 dependency_id: str = None, dependency_type: str = None):
        super().__init__(message, integration_id, 'E013')
        self.dependency_id = dependency_id
        self.dependency_type = dependency_type


class IntegrationCircularDependencyError(IntegrationError):
    """Exception for circular dependency errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 dependency_chain: list = None):
        super().__init__(message, integration_id, 'E014')
        self.dependency_chain = dependency_chain or []


class IntegrationRateLimitError(IntegrationError):
    """Exception for integration rate limit errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 limit_type: str = None, limit_value: int = None, 
                 reset_time: str = None):
        super().__init__(message, integration_id, 'E004')
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.reset_time = reset_time


class IntegrationEndpointUnreachableError(IntegrationError):
    """Exception for unreachable endpoint errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 endpoint: str = None, timeout: int = None):
        super().__init__(message, integration_id, 'E007')
        self.endpoint = endpoint
        self.timeout = timeout


class IntegrationInvalidResponseError(IntegrationError):
    """Exception for invalid response errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 response_code: int = None, response_text: str = None):
        super().__init__(message, integration_id, 'E008')
        self.response_code = response_code
        self.response_text = response_text


class IntegrationConnectionFailedError(IntegrationError):
    """Exception for connection failed errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 connection_type: str = None, error_details: str = None):
        super().__init__(message, integration_id, 'E009')
        self.connection_type = connection_type
        self.error_details = error_details


class IntegrationNotFoundError(IntegrationError):
    """Exception for integration not found errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 integration_type: str = None):
        super().__init__(message, integration_id, 'NOT_FOUND')
        self.integration_type = integration_type


class IntegrationDisabledError(IntegrationError):
    """Exception for integration disabled errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 disabled_reason: str = None):
        super().__init__(message, integration_id, 'DISABLED')
        self.disabled_reason = disabled_reason


class IntegrationPendingError(IntegrationError):
    """Exception for integration pending errors."""
    
    def __init__(self, message: str, integration_id: str = None, 
                 pending_reason: str = None):
        super().__init__(message, integration_id, 'PENDING')
        self.pending_reason = pending_reason


def handle_integration_error(error: Exception, integration_id: str = None, 
                           context: Dict[str, Any] = None) -> IntegrationError:
    """
    Convert generic exception to IntegrationError.
    
    Args:
        error: Generic exception
        integration_id: Integration ID
        context: Additional context
        
    Returns:
        IntegrationError instance
    """
    if isinstance(error, IntegrationError):
        return error
    
    # Create appropriate integration error based on exception type
    error_message = str(error)
    
    if 'timeout' in error_message.lower():
        return IntegrationTimeoutError(error_message, integration_id)
    elif 'connection' in error_message.lower():
        return IntegrationConnectionError(error_message, integration_id)
    elif 'authentication' in error_message.lower():
        return IntegrationAuthenticationError(error_message, integration_id)
    elif 'authorization' in error_message.lower():
        return IntegrationAuthorizationError(error_message, integration_id)
    elif 'validation' in error_message.lower():
        return IntegrationValidationError(error_message, integration_id)
    elif 'not found' in error_message.lower():
        return IntegrationNotFoundError(error_message, integration_id)
    else:
        return IntegrationError(error_message, integration_id, context=context)


def create_error_response(error: IntegrationError) -> Dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        error: IntegrationError instance
        
    Returns:
        Standardized error response
    """
    return {
        'success': False,
        'error': error.message,
        'error_code': getattr(error, 'error_code', 'UNKNOWN'),
        'integration_id': getattr(error, 'integration_id', None),
        'context': getattr(error, 'context', {}),
        'timestamp': getattr(error, 'timestamp', timezone.now().isoformat())
    }

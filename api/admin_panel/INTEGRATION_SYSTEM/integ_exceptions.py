# api/admin_panel/INTEGRATION_SYSTEM/integ_exceptions.py
"""
Integration System Exceptions — all custom exceptions for the integration layer.
"""


class IntegrationBaseError(Exception):
    """Base exception for all integration errors."""
    code = 'INTEGRATION_ERROR'
    http_status = 500

    def __init__(self, message: str = '', details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {'error': self.code, 'message': self.message, 'details': self.details}


class AppNotRegisteredError(IntegrationBaseError):
    """Raised when trying to use an app that isn't in the registry."""
    code = 'APP_NOT_REGISTERED'
    http_status = 404


class CapabilityNotSupportedError(IntegrationBaseError):
    """App doesn't support the requested capability."""
    code = 'CAPABILITY_NOT_SUPPORTED'
    http_status = 403


class IntegrationTimeoutError(IntegrationBaseError):
    """Integration call timed out."""
    code = 'INTEGRATION_TIMEOUT'
    http_status = 504


class IntegrationError(IntegrationBaseError):
    """Generic integration error."""
    code = 'INTEGRATION_ERROR'
    http_status = 500


class AdapterError(IntegrationBaseError):
    """Error from an app adapter."""
    code = 'ADAPTER_ERROR'
    http_status = 500


class DataBridgeError(IntegrationBaseError):
    """Error during data sync."""
    code = 'DATA_BRIDGE_ERROR'
    http_status = 500


class ValidationError(IntegrationBaseError):
    """Data validation failure."""
    code = 'VALIDATION_ERROR'
    http_status = 400

    def __init__(self, message: str = '', errors: list = None):
        super().__init__(message)
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {'error': self.code, 'message': self.message, 'errors': self.errors}


class AuthBridgeError(IntegrationBaseError):
    """Cross-module authentication/permission error."""
    code = 'AUTH_BRIDGE_ERROR'
    http_status = 403


class CircuitBreakerOpenError(IntegrationBaseError):
    """Circuit breaker is open — app is unreachable."""
    code = 'CIRCUIT_BREAKER_OPEN'
    http_status = 503


class RateLimitExceededError(IntegrationBaseError):
    """Rate limit exceeded for integration call."""
    code = 'RATE_LIMIT_EXCEEDED'
    http_status = 429


class SyncConflictError(IntegrationBaseError):
    """Data sync conflict detected."""
    code = 'SYNC_CONFLICT'
    http_status = 409

    def __init__(self, message: str, source: dict = None, target: dict = None):
        super().__init__(message)
        self.source = source or {}
        self.target = target or {}


class DeadLetterError(IntegrationBaseError):
    """Message sent to dead letter queue after exhausting retries."""
    code = 'DEAD_LETTER'
    http_status = 500


class HealthCheckFailedError(IntegrationBaseError):
    """Health check failed for an app."""
    code = 'HEALTH_CHECK_FAILED'
    http_status = 503

    def __init__(self, app: str, status: str = 'down', details: dict = None):
        super().__init__(f"Health check failed for '{app}': {status}")
        self.app = app
        self.status = status
        self.details = details or {}
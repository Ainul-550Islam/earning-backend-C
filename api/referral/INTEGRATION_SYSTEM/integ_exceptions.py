# api/referral/INTEGRATION_SYSTEM/integ_exceptions.py
# Custom exceptions for integration layer
# ============================================================


class IntegrationError(Exception):
    """Base exception for all integration errors."""
    code: str = 'integration_error'
    def __init__(self, message: str = '', code: str = ''):
        super().__init__(message)
        if code:
            self.code = code


class ModuleUnavailableError(IntegrationError):
    """Raised when a required module is not available."""
    code = 'module_unavailable'
    def __init__(self, module: str, detail: str = ''):
        super().__init__(f'Module unavailable: {module}. {detail}')
        self.module = module


class AdapterError(IntegrationError):
    """Raised when an adapter operation fails."""
    code = 'adapter_error'


class HandlerError(IntegrationError):
    """Raised when an event handler fails."""
    code = 'handler_error'


class BridgeError(IntegrationError):
    """Raised when bridge operation fails."""
    code = 'bridge_error'


class EventBusError(IntegrationError):
    """Raised when event bus operation fails."""
    code = 'event_bus_error'


class ValidationError(IntegrationError):
    """Raised when integration data validation fails."""
    code = 'validation_error'
    def __init__(self, message: str = '', fields: dict = None):
        super().__init__(message)
        self.fields = fields or {}


class SyncConflictError(IntegrationError):
    """Raised when data sync conflict is detected."""
    code = 'sync_conflict'
    def __init__(self, message: str = '', conflicting_ids: list = None):
        super().__init__(message)
        self.conflicting_ids = conflicting_ids or []


class CircuitBreakerOpenError(IntegrationError):
    """Raised when circuit breaker is open (service down)."""
    code = 'circuit_breaker_open'
    def __init__(self, service: str = ''):
        super().__init__(f'Circuit breaker open for: {service}')
        self.service = service


class RateLimitExceededError(IntegrationError):
    """Raised when integration rate limit is exceeded."""
    code = 'rate_limit_exceeded'


class AuthBridgeError(IntegrationError):
    """Raised when cross-module permission check fails."""
    code = 'auth_bridge_error'
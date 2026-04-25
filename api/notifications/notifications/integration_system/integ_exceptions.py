# integration_system/integ_exceptions.py
"""
Integration System — Custom Exceptions

All exceptions raised by the integration layer.
Structured with error codes, module context, and retry hints.
"""

from typing import Optional, Dict, Any


class IntegrationBaseException(Exception):
    """Base class for all integration exceptions."""

    def __init__(
        self,
        message: str = '',
        error_code: str = 'E001',
        module: str = '',
        details: Optional[Dict] = None,
        retryable: bool = False,
        original_exc: Optional[Exception] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.module = module
        self.details = details or {}
        self.retryable = retryable
        self.original_exc = original_exc
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_code': self.error_code,
            'message': self.message,
            'module': self.module,
            'details': self.details,
            'retryable': self.retryable,
            'type': type(self).__name__,
        }

    def __str__(self):
        parts = [f'[{self.error_code}]']
        if self.module:
            parts.append(f'({self.module})')
        parts.append(self.message)
        return ' '.join(parts)


# ---------------------------------------------------------------------------
# Registry Exceptions
# ---------------------------------------------------------------------------

class IntegrationNotRegistered(IntegrationBaseException):
    """Raised when trying to use an integration that hasn't been registered."""
    def __init__(self, name: str, **kwargs):
        super().__init__(
            message=f"Integration '{name}' is not registered.",
            error_code='I001',
            **kwargs,
        )


class IntegrationDisabled(IntegrationBaseException):
    """Raised when trying to use a disabled integration."""
    def __init__(self, name: str, **kwargs):
        super().__init__(
            message=f"Integration '{name}' is disabled.",
            error_code='I002',
            **kwargs,
        )


class AdapterNotFound(IntegrationBaseException):
    """Raised when an adapter for a module/service is not found."""
    def __init__(self, service: str, **kwargs):
        super().__init__(
            message=f"No adapter found for service '{service}'.",
            error_code='I003',
            **kwargs,
        )


class DuplicateIntegration(IntegrationBaseException):
    """Raised when trying to register an integration with a duplicate name."""
    def __init__(self, name: str, **kwargs):
        super().__init__(
            message=f"Integration '{name}' is already registered.",
            error_code='I005',
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Bridge / Bus Exceptions
# ---------------------------------------------------------------------------

class BridgeConnectionFailed(IntegrationBaseException):
    """Raised when a bridge connection between two modules fails."""
    def __init__(self, source: str, target: str, reason: str = '', **kwargs):
        super().__init__(
            message=f"Bridge connection from '{source}' to '{target}' failed. {reason}",
            error_code='I004',
            retryable=True,
            **kwargs,
        )


class EventBusPublishFailed(IntegrationBaseException):
    """Raised when publishing an event to the event bus fails."""
    def __init__(self, event: str, reason: str = '', **kwargs):
        super().__init__(
            message=f"Failed to publish event '{event}'. {reason}",
            error_code='I005',
            retryable=True,
            **kwargs,
        )


class EventHandlerFailed(IntegrationBaseException):
    """Raised when an event handler raises an exception."""
    def __init__(self, event: str, handler: str, reason: str = '', **kwargs):
        super().__init__(
            message=f"Event handler '{handler}' failed for event '{event}'. {reason}",
            error_code='I005',
            retryable=False,
            **kwargs,
        )


class MessageQueueFull(IntegrationBaseException):
    """Raised when the message queue is at capacity."""
    def __init__(self, queue: str = 'default', **kwargs):
        super().__init__(
            message=f"Message queue '{queue}' is full. Try again later.",
            error_code='E004',
            retryable=True,
            **kwargs,
        )


class MessageQueueTimeout(IntegrationBaseException):
    """Raised when a queued message is not processed within the allowed time."""
    def __init__(self, message_id: str = '', **kwargs):
        super().__init__(
            message=f"Message '{message_id}' processing timed out.",
            error_code='E003',
            retryable=True,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Webhook Exceptions
# ---------------------------------------------------------------------------

class WebhookVerificationFailed(IntegrationBaseException):
    """Raised when webhook signature verification fails."""
    def __init__(self, provider: str = '', **kwargs):
        super().__init__(
            message=f"Webhook signature verification failed for provider '{provider}'.",
            error_code='A001',
            retryable=False,
            **kwargs,
        )


class WebhookProcessingFailed(IntegrationBaseException):
    """Raised when webhook payload processing fails."""
    def __init__(self, event_type: str = '', reason: str = '', **kwargs):
        super().__init__(
            message=f"Webhook processing failed for event '{event_type}'. {reason}",
            error_code='I006',
            retryable=True,
            **kwargs,
        )


class DuplicateWebhook(IntegrationBaseException):
    """Raised when a duplicate webhook event is detected (idempotency check)."""
    def __init__(self, idempotency_key: str = '', **kwargs):
        super().__init__(
            message=f"Duplicate webhook detected: '{idempotency_key}'.",
            error_code='D005',
            retryable=False,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Data Exceptions
# ---------------------------------------------------------------------------

class ValidationFailed(IntegrationBaseException):
    """Raised when data validation fails."""
    def __init__(self, field: str = '', reason: str = '', **kwargs):
        msg = f"Validation failed"
        if field:
            msg += f" for field '{field}'"
        if reason:
            msg += f": {reason}"
        super().__init__(message=msg, error_code='D001', **kwargs)


class DataTypeMismatch(IntegrationBaseException):
    """Raised when data type doesn't match expected type."""
    def __init__(self, field: str, expected: str, got: str, **kwargs):
        super().__init__(
            message=f"Type mismatch for '{field}': expected {expected}, got {got}.",
            error_code='D002',
            **kwargs,
        )


class RequiredFieldMissing(IntegrationBaseException):
    """Raised when a required field is missing."""
    def __init__(self, field: str, **kwargs):
        super().__init__(
            message=f"Required field '{field}' is missing.",
            error_code='D003',
            **kwargs,
        )


class DataTransformationFailed(IntegrationBaseException):
    """Raised when data transformation/mapping fails."""
    def __init__(self, source: str, target: str, reason: str = '', **kwargs):
        super().__init__(
            message=f"Data transformation from '{source}' to '{target}' failed. {reason}",
            error_code='I007',
            **kwargs,
        )


class SyncConflict(IntegrationBaseException):
    """Raised when a data sync conflict is detected."""
    def __init__(self, field: str, source_value: Any, target_value: Any, **kwargs):
        super().__init__(
            message=(
                f"Sync conflict on field '{field}': "
                f"source='{source_value}' vs target='{target_value}'."
            ),
            error_code='I008',
            retryable=False,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Auth Exceptions
# ---------------------------------------------------------------------------

class CrossModulePermissionDenied(IntegrationBaseException):
    """Raised when a module doesn't have permission to access another module's data."""
    def __init__(self, source_module: str, target_module: str, action: str = '', **kwargs):
        super().__init__(
            message=(
                f"Module '{source_module}' does not have permission "
                f"to {action or 'access'} '{target_module}'."
            ),
            error_code='A002',
            retryable=False,
            **kwargs,
        )


class InvalidAPIKey(IntegrationBaseException):
    """Raised when an API key is invalid or revoked."""
    def __init__(self, service: str = '', **kwargs):
        super().__init__(
            message=f"Invalid or revoked API key for service '{service}'.",
            error_code='A004',
            retryable=False,
            **kwargs,
        )


class TokenExpired(IntegrationBaseException):
    """Raised when an auth token has expired."""
    def __init__(self, service: str = '', **kwargs):
        super().__init__(
            message=f"Auth token expired for service '{service}'.",
            error_code='A003',
            retryable=True,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Service / Availability Exceptions
# ---------------------------------------------------------------------------

class ServiceUnavailable(IntegrationBaseException):
    """Raised when an external service is unavailable."""
    def __init__(self, service: str, **kwargs):
        super().__init__(
            message=f"Service '{service}' is currently unavailable.",
            error_code='E002',
            retryable=True,
            **kwargs,
        )


class RateLimitExceeded(IntegrationBaseException):
    """Raised when a rate limit is exceeded."""
    def __init__(self, service: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message=f"Rate limit exceeded for '{service}'. Retry after {retry_after}s.",
            error_code='E004',
            retryable=True,
            details={'retry_after': retry_after},
            **kwargs,
        )


class IntegrationTimeout(IntegrationBaseException):
    """Raised when an integration operation times out."""
    def __init__(self, operation: str, timeout: int = 30, **kwargs):
        super().__init__(
            message=f"Integration operation '{operation}' timed out after {timeout}s.",
            error_code='E003',
            retryable=True,
            **kwargs,
        )


class FallbackFailed(IntegrationBaseException):
    """Raised when both the primary and fallback operations fail."""
    def __init__(self, operation: str, **kwargs):
        super().__init__(
            message=f"Both primary and fallback failed for operation '{operation}'.",
            error_code='E002',
            retryable=False,
            **kwargs,
        )


class HealthCheckFailed(IntegrationBaseException):
    """Raised when a service health check fails."""
    def __init__(self, service: str, **kwargs):
        super().__init__(
            message=f"Health check failed for service '{service}'.",
            error_code='E002',
            retryable=True,
            **kwargs,
        )

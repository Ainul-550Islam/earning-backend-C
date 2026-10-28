# api/djoyalty/integration_system/integ_exceptions.py
"""
Integration System Exceptions।
All integration-specific exceptions with proper hierarchy।
"""


class DjoyaltyIntegrationError(Exception):
    """Base class for all Djoyalty integration errors।"""
    def __init__(self, message: str = '', integration_name: str = '',
                 status_code: int = None, response_data: dict = None):
        self.integration_name = integration_name
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            'error': self.__class__.__name__,
            'message': str(self),
            'integration': self.integration_name,
            'status_code': self.status_code,
        }


# ─── Connection Errors ────────────────────────────────────────────────────────

class IntegrationConnectionError(DjoyaltyIntegrationError):
    """Cannot connect to external service।"""
    pass


class IntegrationTimeoutError(IntegrationConnectionError):
    """Request timed out।"""
    pass


class IntegrationSSLError(IntegrationConnectionError):
    """SSL/TLS connection error।"""
    pass


# ─── Authentication Errors ────────────────────────────────────────────────────

class IntegrationAuthError(DjoyaltyIntegrationError):
    """Authentication/authorization failed।"""
    pass


class InvalidAPIKeyError(IntegrationAuthError):
    """Invalid or expired API key।"""
    pass


class TokenExpiredError(IntegrationAuthError):
    """Auth token expired।"""
    pass


class InsufficientPermissionError(IntegrationAuthError):
    """Not enough permissions for this operation।"""
    pass


# ─── Configuration Errors ────────────────────────────────────────────────────

class IntegrationNotConfiguredError(DjoyaltyIntegrationError):
    """Integration not configured in settings।"""
    def __init__(self, integration_name: str):
        super().__init__(
            f'{integration_name} integration is not configured. '
            f'Please add {integration_name.upper()} settings.',
            integration_name=integration_name,
        )


class IntegrationDisabledError(DjoyaltyIntegrationError):
    """Integration is disabled।"""
    pass


class MissingConfigError(DjoyaltyIntegrationError):
    """Required configuration key is missing।"""
    def __init__(self, key: str, integration_name: str = ''):
        super().__init__(
            f'Missing required config: {key}',
            integration_name=integration_name,
        )
        self.config_key = key


# ─── Circuit Breaker Errors ───────────────────────────────────────────────────

class CircuitBreakerOpenError(DjoyaltyIntegrationError):
    """Circuit breaker is open -- service is down।"""
    def __init__(self, integration_name: str, retry_after: int = 60):
        super().__init__(
            f'{integration_name} circuit breaker is OPEN. '
            f'Retry after {retry_after} seconds.',
            integration_name=integration_name,
        )
        self.retry_after = retry_after


class CircuitBreakerTrippedError(CircuitBreakerOpenError):
    """Circuit breaker just tripped due to failures।"""
    pass


# ─── Rate Limit Errors ────────────────────────────────────────────────────────

class RateLimitExceededError(DjoyaltyIntegrationError):
    """API rate limit exceeded।"""
    def __init__(self, integration_name: str = '', retry_after: int = 60):
        super().__init__(
            f'Rate limit exceeded for {integration_name}. '
            f'Retry after {retry_after}s.',
            integration_name=integration_name,
        )
        self.retry_after = retry_after


# ─── Data Errors ─────────────────────────────────────────────────────────────

class IntegrationDataError(DjoyaltyIntegrationError):
    """Data validation or transformation error।"""
    pass


class InvalidPostbackError(IntegrationDataError):
    """Postback signature validation failed।"""
    pass


class DuplicateTransactionError(IntegrationDataError):
    """Transaction already processed।"""
    def __init__(self, transaction_id: str):
        super().__init__(f'Duplicate transaction: {transaction_id}')
        self.transaction_id = transaction_id


class InvalidCurrencyError(IntegrationDataError):
    """Currency not supported।"""
    pass


# ─── Webhook Errors ──────────────────────────────────────────────────────────

class WebhookDeliveryError(DjoyaltyIntegrationError):
    """Webhook delivery failed।"""
    def __init__(self, url: str, status_code: int = None, attempt: int = 1):
        super().__init__(
            f'Webhook delivery failed: {url} (HTTP {status_code}, attempt {attempt})',
            status_code=status_code,
        )
        self.url = url
        self.attempt = attempt


class WebhookMaxRetriesError(WebhookDeliveryError):
    """Max webhook retries exceeded।"""
    pass


# ─── Queue Errors ────────────────────────────────────────────────────────────

class MessageQueueError(DjoyaltyIntegrationError):
    """Message queue operation failed।"""
    pass


class QueueFullError(MessageQueueError):
    """Message queue is full।"""
    pass


class MessageProcessingError(MessageQueueError):
    """Error processing message from queue।"""
    pass


# ─── Sync Errors ─────────────────────────────────────────────────────────────

class DataSyncConflictError(DjoyaltyIntegrationError):
    """Data sync conflict detected।"""
    def __init__(self, model: str, object_id, server_version, client_version):
        super().__init__(
            f'Sync conflict on {model}#{object_id}: '
            f'server={server_version}, client={client_version}',
        )
        self.model = model
        self.object_id = object_id
        self.server_version = server_version
        self.client_version = client_version


class SyncLockError(DjoyaltyIntegrationError):
    """Cannot acquire sync lock।"""
    pass


# ─── Helper ───────────────────────────────────────────────────────────────────

def handle_requests_exception(exc, integration_name: str = '') -> DjoyaltyIntegrationError:
    """Convert requests library exception to DjoyaltyIntegrationError।"""
    try:
        import requests.exceptions as req_exc
        if isinstance(exc, req_exc.Timeout):
            return IntegrationTimeoutError(str(exc), integration_name=integration_name)
        elif isinstance(exc, req_exc.SSLError):
            return IntegrationSSLError(str(exc), integration_name=integration_name)
        elif isinstance(exc, req_exc.ConnectionError):
            return IntegrationConnectionError(str(exc), integration_name=integration_name)
        elif isinstance(exc, req_exc.HTTPError):
            sc = exc.response.status_code if exc.response else None
            if sc == 401:
                return IntegrationAuthError(str(exc), integration_name=integration_name, status_code=sc)
            elif sc == 429:
                return RateLimitExceededError(integration_name=integration_name)
            return DjoyaltyIntegrationError(str(exc), integration_name=integration_name, status_code=sc)
    except ImportError:
        pass
    return DjoyaltyIntegrationError(str(exc), integration_name=integration_name)

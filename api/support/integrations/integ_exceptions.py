# api/support/integrations/integ_exceptions.py  — WORLD #1
"""Custom exceptions for integration system."""


class IntegrationError(Exception):
    """Base integration exception"""
    def __init__(self, message: str = '', code: str = 'integration_error', adapter: str = ''):
        self.message = message
        self.code    = code
        self.adapter = adapter
        super().__init__(message)


class AdapterNotAvailableError(IntegrationError):
    """Adapter/app not installed or not reachable"""
    def __init__(self, adapter: str):
        super().__init__(f'Integration adapter not available: {adapter}', 'adapter_unavailable', adapter)


class InsufficientBalanceError(IntegrationError):
    """Wallet balance insufficient"""
    def __init__(self, required=0, available=0):
        super().__init__(f'Insufficient balance. Required: {required}, Available: {available}', 'insufficient_balance')
        self.required  = required
        self.available = available


class WalletLockedError(IntegrationError):
    """Wallet is locked"""
    def __init__(self, reason: str = ''):
        super().__init__(f'Wallet is locked: {reason}', 'wallet_locked')


class FraudRiskTooHighError(IntegrationError):
    """Fraud risk score too high for auto-approval"""
    def __init__(self, score: int = 0):
        super().__init__(f'Fraud risk score too high: {score}', 'fraud_risk_high')
        self.score = score


class DisputeLimitExceededError(IntegrationError):
    """User has exceeded dispute limit"""
    def __init__(self, limit: int = 0, period: str = 'week'):
        super().__init__(f'Dispute limit ({limit}/{period}) exceeded', 'dispute_limit_exceeded')


class VerificationFailedError(IntegrationError):
    """Offer/payment verification failed"""
    def __init__(self, reason: str = ''):
        super().__init__(f'Verification failed: {reason}', 'verification_failed')


class EventBusError(IntegrationError):
    """Event bus publish/subscribe error"""
    def __init__(self, event: str = '', reason: str = ''):
        super().__init__(f'Event bus error [{event}]: {reason}', 'event_bus_error')


class WebhookError(IntegrationError):
    """Webhook delivery failed"""
    def __init__(self, url: str = '', status_code: int = 0):
        super().__init__(f'Webhook failed: {url} → {status_code}', 'webhook_error')
        self.status_code = status_code


class HealthCheckFailed(IntegrationError):
    """Integration health check failed"""
    def __init__(self, integration: str = ''):
        super().__init__(f'Health check failed: {integration}', 'health_check_failed')


class SyncConflictError(IntegrationError):
    """Data sync conflict between systems"""
    def __init__(self, field: str = '', source: str = '', target: str = ''):
        super().__init__(f'Sync conflict on field {field}: {source} vs {target}', 'sync_conflict')
        self.field  = field
        self.source = source
        self.target = target
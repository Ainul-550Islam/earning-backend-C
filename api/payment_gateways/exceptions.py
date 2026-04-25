# api/payment_gateways/exceptions.py — Custom exceptions

class PaymentGatewayError(Exception):
    """Base payment gateway exception."""
    def __init__(self, message='Payment gateway error', code='GATEWAY_ERROR', gateway=None):
        self.message = message
        self.code    = code
        self.gateway = gateway
        super().__init__(message)

class GatewayAuthError(PaymentGatewayError):
    """Authentication failed (wrong API key)."""
    def __init__(self, gateway=None):
        super().__init__('Gateway authentication failed', 'AUTH_ERROR', gateway)

class GatewayTimeoutError(PaymentGatewayError):
    """Gateway API timeout."""
    def __init__(self, gateway=None):
        super().__init__('Gateway request timed out', 'TIMEOUT', gateway)

class GatewayDownError(PaymentGatewayError):
    """Gateway is down."""
    def __init__(self, gateway=None):
        super().__init__('Gateway is currently unavailable', 'GATEWAY_DOWN', gateway)

class InvalidAmountError(PaymentGatewayError):
    """Amount out of range."""
    def __init__(self, msg='Invalid amount'):
        super().__init__(msg, 'INVALID_AMOUNT')

class DuplicateTransactionError(PaymentGatewayError):
    """Duplicate transaction detected."""
    def __init__(self):
        super().__init__('Duplicate transaction', 'DUPLICATE_TXN')

class FraudDetectedError(PaymentGatewayError):
    """Transaction blocked by fraud detection."""
    def __init__(self, reason=''):
        super().__init__(f'Transaction blocked: {reason}', 'FRAUD_DETECTED')

class InsufficientBalanceError(PaymentGatewayError):
    """User balance too low."""
    def __init__(self):
        super().__init__('Insufficient balance', 'INSUFFICIENT_BALANCE')

class WebhookSignatureError(PaymentGatewayError):
    """Webhook signature verification failed."""
    def __init__(self, gateway=None):
        super().__init__('Invalid webhook signature', 'INVALID_SIGNATURE', gateway)

class RefundNotAllowedError(PaymentGatewayError):
    """Refund not permitted for this transaction."""
    def __init__(self, reason=''):
        super().__init__(f'Refund not allowed: {reason}', 'REFUND_NOT_ALLOWED')

"""
exceptions.py – Custom exceptions for Postback Engine.
"""


class PostbackEngineError(Exception):
    """Base exception for all postback engine errors."""
    default_message = "Postback engine error."
    http_status = 400

    def __init__(self, message: str = None, detail: str = "", code: str = None):
        self.message = message or self.default_message
        self.detail = detail
        self.code = code or self.__class__.__name__
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}" + (f": {self.detail}" if self.detail else "")


# ── Network Errors ────────────────────────────────────────────────────────────

class NetworkNotFoundException(PostbackEngineError):
    default_message = "Network not found."
    http_status = 404


class NetworkInactiveException(PostbackEngineError):
    default_message = "Network is inactive or suspended."
    http_status = 403


class NetworkConfigurationError(PostbackEngineError):
    default_message = "Network is misconfigured."


class AdapterNotFoundError(PostbackEngineError):
    default_message = "No adapter registered for this network."


# ── Security / Validation Errors ──────────────────────────────────────────────

class InvalidSignatureException(PostbackEngineError):
    default_message = "Signature verification failed."
    http_status = 401


class SignatureExpiredException(PostbackEngineError):
    default_message = "Postback timestamp is too old (replay attack prevention)."
    http_status = 401


class NonceReusedException(PostbackEngineError):
    default_message = "Nonce has already been used."
    http_status = 401


class IPNotWhitelistedException(PostbackEngineError):
    default_message = "Source IP is not in the whitelist."
    http_status = 403


class RateLimitExceededException(PostbackEngineError):
    default_message = "Rate limit exceeded."
    http_status = 429

    def __init__(self, message: str = None, retry_after: int = 60, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class SchemaValidationException(PostbackEngineError):
    default_message = "Payload schema validation failed."


class MissingRequiredFieldsException(PostbackEngineError):
    default_message = "One or more required fields are missing."

    def __init__(self, message: str = None, missing_fields: list = None, **kwargs):
        self.missing_fields = missing_fields or []
        super().__init__(message, **kwargs)


# ── Deduplication Errors ──────────────────────────────────────────────────────

class DuplicateLeadException(PostbackEngineError):
    default_message = "Duplicate lead ID detected."

    def __init__(self, message: str = None, first_seen_at=None, **kwargs):
        self.first_seen_at = first_seen_at
        super().__init__(message, **kwargs)


class DuplicateClickException(PostbackEngineError):
    default_message = "Duplicate click ID detected."


class DuplicateConversionException(PostbackEngineError):
    default_message = "Conversion already recorded for this transaction."


# ── Fraud / Blacklist Errors ───────────────────────────────────────────────────

class FraudDetectedException(PostbackEngineError):
    default_message = "Fraud signals detected."
    http_status = 403

    def __init__(self, message: str = None, fraud_score: float = 0, fraud_type: str = "", **kwargs):
        self.fraud_score = fraud_score
        self.fraud_type = fraud_type
        super().__init__(message, **kwargs)


class BlacklistedSourceException(PostbackEngineError):
    default_message = "Source is blacklisted."
    http_status = 403


class BotTrafficException(FraudDetectedException):
    default_message = "Bot traffic detected."


class ProxyVPNDetectedException(FraudDetectedException):
    default_message = "Proxy or VPN detected."


class VelocityLimitException(PostbackEngineError):
    default_message = "Velocity limit exceeded."
    http_status = 429


# ── Business Logic Errors ─────────────────────────────────────────────────────

class UserResolutionException(PostbackEngineError):
    default_message = "Could not resolve user from postback payload."


class UserNotFoundException(PostbackEngineError):
    default_message = "User not found."
    http_status = 404


class OfferNotFoundException(PostbackEngineError):
    default_message = "Offer not found or inactive."
    http_status = 404


class OfferInactiveException(PostbackEngineError):
    default_message = "Offer is not currently active."
    http_status = 403


class ConversionWindowExpiredException(PostbackEngineError):
    default_message = "Conversion window has expired for this click."


class PayoutLimitExceededException(PostbackEngineError):
    default_message = "Payout exceeds maximum allowed limit."

    def __init__(self, message: str = None, payout=None, limit=None, **kwargs):
        self.payout = payout
        self.limit = limit
        super().__init__(message, **kwargs)


class RewardDispatchException(PostbackEngineError):
    default_message = "Failed to dispatch reward."


class WalletException(PostbackEngineError):
    default_message = "Wallet operation failed."


# ── Postback Processing Errors ────────────────────────────────────────────────

class PostbackAlreadyProcessedException(PostbackEngineError):
    default_message = "This postback has already been processed."


class PostbackProcessingException(PostbackEngineError):
    default_message = "Error during postback processing."


class MaxRetriesExceededException(PostbackEngineError):
    default_message = "Maximum retry attempts exceeded."


# ── Click / Tracking Errors ───────────────────────────────────────────────────

class ClickExpiredException(PostbackEngineError):
    default_message = "Click has expired."


class ClickNotFoundException(PostbackEngineError):
    default_message = "Click not found."
    http_status = 404


class InvalidClickException(PostbackEngineError):
    default_message = "Click is invalid."


# ── Queue Errors ──────────────────────────────────────────────────────────────

class QueueFullException(PostbackEngineError):
    default_message = "Processing queue is full."
    http_status = 503


class DeadLetterException(PostbackEngineError):
    default_message = "Item moved to dead letter queue."


# ── Webhook Errors ────────────────────────────────────────────────────────────

class WebhookDeliveryException(PostbackEngineError):
    default_message = "Webhook delivery failed."


class WebhookSignatureException(PostbackEngineError):
    default_message = "Webhook signature verification failed."
    http_status = 401

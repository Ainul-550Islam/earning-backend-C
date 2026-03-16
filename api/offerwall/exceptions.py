"""
Custom exceptions for offerwall system
"""
from rest_framework.exceptions import APIException
from rest_framework import status


class OfferException(APIException):
    """Base exception for offer-related errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An error occurred with the offer'
    default_code = 'offer_error'


class OfferNotFoundException(OfferException):
    """Raised when offer is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Offer not found'
    default_code = 'offer_not_found'


class OfferInactiveException(OfferException):
    """Raised when offer is inactive"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'This offer is not active'
    default_code = 'offer_inactive'


class OfferExpiredException(OfferException):
    """Raised when offer has expired"""
    status_code = status.HTTP_410_GONE
    default_detail = 'This offer has expired'
    default_code = 'offer_expired'


class OfferNotAvailableException(OfferException):
    """Raised when offer is not available for user"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This offer is not available for your account'
    default_code = 'offer_not_available'


class OfferLimitReachedException(OfferException):
    """Raised when user has reached offer completion limit"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'You have reached the limit for this offer'
    default_code = 'offer_limit_reached'


class DailyLimitReachedException(OfferException):
    """Raised when user has reached daily earning limit"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'You have reached your daily earning limit'
    default_code = 'daily_limit_reached'


class OfferCapReachedException(OfferException):
    """Raised when offer's total cap is reached"""
    status_code = status.HTTP_410_GONE
    default_detail = 'This offer has reached its maximum completions'
    default_code = 'offer_cap_reached'


class CountryNotSupportedException(OfferException):
    """Raised when offer is not available in user's country"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This offer is not available in your country'
    default_code = 'country_not_supported'


class PlatformNotSupportedException(OfferException):
    """Raised when offer doesn't support user's platform"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This offer is not available on your platform'
    default_code = 'platform_not_supported'


class ProviderException(APIException):
    """Base exception for provider-related errors"""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Provider service error'
    default_code = 'provider_error'


class ProviderNotFoundException(ProviderException):
    """Raised when provider is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Provider not found'
    default_code = 'provider_not_found'


class ProviderInactiveException(ProviderException):
    """Raised when provider is inactive"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Provider service is currently unavailable'
    default_code = 'provider_inactive'


class ProviderAPIException(ProviderException):
    """Raised when provider API fails"""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Failed to communicate with provider'
    default_code = 'provider_api_error'


class ProviderTimeoutException(ProviderException):
    """Raised when provider API times out"""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = 'Provider request timed out'
    default_code = 'provider_timeout'


class ProviderAuthenticationException(ProviderException):
    """Raised when provider authentication fails"""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Provider authentication failed'
    default_code = 'provider_auth_failed'


class InvalidProviderConfigException(ProviderException):
    """Raised when provider configuration is invalid"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Invalid provider configuration'
    default_code = 'invalid_provider_config'


class ConversionException(APIException):
    """Base exception for conversion-related errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Conversion error'
    default_code = 'conversion_error'


class DuplicateConversionException(ConversionException):
    """Raised when duplicate conversion is detected"""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Duplicate conversion detected'
    default_code = 'duplicate_conversion'


class InvalidConversionException(ConversionException):
    """Raised when conversion data is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid conversion data'
    default_code = 'invalid_conversion'


class ConversionNotFoundException(ConversionException):
    """Raised when conversion is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Conversion not found'
    default_code = 'conversion_not_found'


class ConversionAlreadyProcessedException(ConversionException):
    """Raised when conversion has already been processed"""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This conversion has already been processed'
    default_code = 'conversion_already_processed'


class WebhookException(APIException):
    """Base exception for webhook-related errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Webhook error'
    default_code = 'webhook_error'


class InvalidWebhookSignatureException(WebhookException):
    """Raised when webhook signature is invalid"""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid webhook signature'
    default_code = 'invalid_webhook_signature'


class WebhookTimestampException(WebhookException):
    """Raised when webhook timestamp is too old"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Webhook timestamp is too old'
    default_code = 'invalid_webhook_timestamp'


class InvalidWebhookDataException(WebhookException):
    """Raised when webhook data is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid webhook data'
    default_code = 'invalid_webhook_data'


class FraudException(APIException):
    """Base exception for fraud-related errors"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Fraudulent activity detected'
    default_code = 'fraud_detected'


class SuspiciousActivityException(FraudException):
    """Raised when suspicious activity is detected"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Suspicious activity detected on your account'
    default_code = 'suspicious_activity'


class VPNDetectedException(FraudException):
    """Raised when VPN/Proxy is detected"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'VPN/Proxy usage is not allowed'
    default_code = 'vpn_detected'


class MultiAccountException(FraudException):
    """Raised when multiple accounts are detected"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Multiple account usage detected'
    default_code = 'multi_account_detected'


class ClickFraudException(FraudException):
    """Raised when click fraud is detected"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Click fraud detected'
    default_code = 'click_fraud'


class AccountSuspendedException(FraudException):
    """Raised when account is suspended"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Your account has been suspended'
    default_code = 'account_suspended'


class AccountBannedException(FraudException):
    """Raised when account is banned"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Your account has been permanently banned'
    default_code = 'account_banned'


class ValidationException(APIException):
    """Base exception for validation errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Validation error'
    default_code = 'validation_error'


class InvalidParameterException(ValidationException):
    """Raised when parameter is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid parameter'
    default_code = 'invalid_parameter'


class MissingParameterException(ValidationException):
    """Raised when required parameter is missing"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Missing required parameter'
    default_code = 'missing_parameter'


class InvalidIPAddressException(ValidationException):
    """Raised when IP address is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid IP address'
    default_code = 'invalid_ip_address'


class RateLimitException(APIException):
    """Raised when rate limit is exceeded"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded. Please try again later.'
    default_code = 'rate_limit_exceeded'


class ServiceException(APIException):
    """Base exception for service errors"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Internal service error'
    default_code = 'service_error'


class DatabaseException(ServiceException):
    """Raised when database operation fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Database operation failed'
    default_code = 'database_error'


class CacheException(ServiceException):
    """Raised when cache operation fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Cache operation failed'
    default_code = 'cache_error'


class ConfigurationException(ServiceException):
    """Raised when configuration is invalid"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Invalid configuration'
    default_code = 'config_error'


class SyncException(ServiceException):
    """Raised when sync operation fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Sync operation failed'
    default_code = 'sync_error'


class TransactionException(APIException):
    """Base exception for transaction errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Transaction error'
    default_code = 'transaction_error'


class InsufficientBalanceException(TransactionException):
    """Raised when user has insufficient balance"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Insufficient balance'
    default_code = 'insufficient_balance'


class TransactionFailedException(TransactionException):
    """Raised when transaction fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Transaction failed'
    default_code = 'transaction_failed'


class RewardException(APIException):
    """Base exception for reward errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Reward error'
    default_code = 'reward_error'


class InvalidRewardException(RewardException):
    """Raised when reward amount is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid reward amount'
    default_code = 'invalid_reward'


class RewardCreditException(RewardException):
    """Raised when reward crediting fails"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Failed to credit reward'
    default_code = 'reward_credit_failed'


# Helper function to format exception messages
def format_exception_message(message: str, **kwargs) -> str:
    """
    Format exception message with parameters
    
    Args:
        message: Base message with placeholders
        **kwargs: Parameters to fill placeholders
    
    Returns:
        Formatted message string
    """
    try:
        return message.format(**kwargs)
    except (KeyError, IndexError):
        return message


# Helper function to create custom exception
def create_exception(
    exception_class,
    message: str = None,
    code: str = None,
    status_code: int = None
):
    """
    Create a custom exception instance
    
    Args:
        exception_class: Exception class to instantiate
        message: Custom error message
        code: Custom error code
        status_code: Custom HTTP status code
    
    Returns:
        Exception instance
    """
    exc = exception_class()
    
    if message:
        exc.detail = message
    
    if code:
        exc.default_code = code
    
    if status_code:
        exc.status_code = status_code
    
    return exc
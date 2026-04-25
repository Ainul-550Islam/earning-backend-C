# api/ad_networks/exceptions.py
# System-Level Exception Classes Only

from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.exceptions import APIException
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# BASE SYSTEM EXCEPTIONS
# ============================================================================

class AdNetworksBaseException(Exception):
    """Base exception for Ad Networks module"""
    
    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)
    
    def __str__(self):
        return self.message

# ============================================================================
# VALIDATION EXCEPTIONS
# ============================================================================

class ValidationException(AdNetworksBaseException):
    """Custom validation exception"""
    
    def __init__(self, message, field=None, value=None):
        super().__init__(message, 'validation_error')
        self.field = field
        self.value = value

class FileUploadException(AdNetworksBaseException):
    """File upload related exception"""
    
    def __init__(self, message, file_type=None, file_size=None):
        super().__init__(message, 'file_upload_error')
        self.file_type = file_type
        self.file_size = file_size

class SecurityValidationException(AdNetworksBaseException):
    """Security validation exception"""
    
    def __init__(self, message, security_type=None):
        super().__init__(message, 'security_validation_error')
        self.security_type = security_type

# ============================================================================
# BUSINESS LOGIC EXCEPTIONS
# ============================================================================

class OfferException(AdNetworksBaseException):
    """Offer related exception"""
    
    def __init__(self, message, offer_id=None):
        super().__init__(message, 'offer_error')
        self.offer_id = offer_id

class OfferNotAvailableException(OfferException):
    """Offer not available exception"""
    
    def __init__(self, message="Offer is not available", offer_id=None):
        super().__init__(message, offer_id)

class OfferExpiredException(OfferException):
    """Offer expired exception"""
    
    def __init__(self, message="Offer has expired", offer_id=None):
        super().__init__(message, offer_id)

class InsufficientRewardException(OfferException):
    """Insufficient reward exception"""
    
    def __init__(self, message="Insufficient reward amount", offer_id=None):
        super().__init__(message, offer_id)

class UserEngagementException(AdNetworksBaseException):
    """User engagement exception"""
    
    def __init__(self, message, user_id=None, offer_id=None):
        super().__init__(message, 'engagement_error')
        self.user_id = user_id
        self.offer_id = offer_id

class EngagementAlreadyCompletedException(UserEngagementException):
    """Engagement already completed exception"""
    
    def __init__(self, message="Engagement already completed", user_id=None, offer_id=None):
        super().__init__(message, user_id, offer_id)

class DailyLimitExceededException(UserEngagementException):
    """Daily limit exceeded exception"""
    
    def __init__(self, message="Daily limit exceeded", user_id=None, offer_id=None):
        super().__init__(message, user_id, offer_id)

# ============================================================================
# CONVERSION EXCEPTIONS
# ============================================================================

class ConversionException(AdNetworksBaseException):
    """Conversion related exception"""
    
    def __init__(self, message, conversion_id=None):
        super().__init__(message, 'conversion_error')
        self.conversion_id = conversion_id

class ConversionValidationException(ConversionException):
    """Conversion validation exception"""
    
    def __init__(self, message="Conversion validation failed", conversion_id=None):
        super().__init__(message, conversion_id)

class ConversionAlreadyProcessedException(ConversionException):
    """Conversion already processed exception"""
    
    def __init__(self, message="Conversion already processed", conversion_id=None):
        super().__init__(message, conversion_id)

# ============================================================================
# PAYMENT EXCEPTIONS
# ============================================================================

class PaymentException(AdNetworksBaseException):
    """Payment related exception"""
    
    def __init__(self, message, payment_id=None, amount=None):
        super().__init__(message, 'payment_error')
        self.payment_id = payment_id
        self.amount = amount

class InsufficientFundsException(PaymentException):
    """Insufficient funds exception"""
    
    def __init__(self, message="Insufficient funds", payment_id=None, amount=None):
        super().__init__(message, payment_id, amount)

class PaymentProcessingException(PaymentException):
    """Payment processing exception"""
    
    def __init__(self, message="Payment processing failed", payment_id=None, amount=None):
        super().__init__(message, payment_id, amount)

class PaymentTimeoutException(PaymentException):
    """Payment timeout exception"""
    
    def __init__(self, message="Payment processing timeout", payment_id=None, amount=None):
        super().__init__(message, payment_id, amount)

# ============================================================================
# FRAUD DETECTION EXCEPTIONS
# ============================================================================

class FraudDetectionException(AdNetworksBaseException):
    """Fraud detection exception"""
    
    def __init__(self, message, fraud_score=None, fraud_type=None):
        super().__init__(message, 'fraud_detection_error')
        self.fraud_score = fraud_score
        self.fraud_type = fraud_type

class HighFraudScoreException(FraudDetectionException):
    """High fraud score exception"""
    
    def __init__(self, message="High fraud score detected", fraud_score=None, fraud_type=None):
        super().__init__(message, fraud_score, fraud_type)

class SuspiciousActivityException(FraudDetectionException):
    """Suspicious activity exception"""
    
    def __init__(self, message="Suspicious activity detected", fraud_score=None, fraud_type=None):
        super().__init__(message, fraud_score, fraud_type)

class IPBlacklistedException(FraudDetectionException):
    """IP blacklisted exception"""
    
    def __init__(self, message="IP address is blacklisted", fraud_score=None, fraud_type='ip_blacklist'):
        super().__init__(message, fraud_score, fraud_type)

# ============================================================================
# NETWORK EXCEPTIONS
# ============================================================================

class NetworkException(AdNetworksBaseException):
    """Network related exception"""
    
    def __init__(self, message, network_id=None):
        super().__init__(message, 'network_error')
        self.network_id = network_id

class NetworkConnectivityException(NetworkException):
    """Network connectivity exception"""
    
    def __init__(self, message="Network connectivity failed", network_id=None):
        super().__init__(message, network_id)

class NetworkTimeoutException(NetworkException):
    """Network timeout exception"""
    
    def __init__(self, message="Network request timeout", network_id=None):
        super().__init__(message, network_id)

class NetworkAPIException(NetworkException):
    """Network API exception"""
    
    def __init__(self, message="Network API error", network_id=None, api_response=None):
        super().__init__(message, network_id)
        self.api_response = api_response

# ============================================================================
# TENANT EXCEPTIONS
# ============================================================================

class TenantException(AdNetworksBaseException):
    """Tenant related exception"""
    
    def __init__(self, message, tenant_id=None):
        super().__init__(message, 'tenant_error')
        self.tenant_id = tenant_id

class TenantNotFoundException(TenantException):
    """Tenant not found exception"""
    
    def __init__(self, message="Tenant not found", tenant_id=None):
        super().__init__(message, tenant_id)

class TenantSuspendedException(TenantException):
    """Tenant suspended exception"""
    
    def __init__(self, message="Tenant is suspended", tenant_id=None):
        super().__init__(message, tenant_id)

class TenantLimitExceededException(TenantException):
    """Tenant limit exceeded exception"""
    
    def __init__(self, message="Tenant limit exceeded", tenant_id=None, limit_type=None):
        super().__init__(message, tenant_id)
        self.limit_type = limit_type

# ============================================================================
# CACHE EXCEPTIONS
# ============================================================================

class CacheException(AdNetworksBaseException):
    """Cache related exception"""
    
    def __init__(self, message, cache_key=None):
        super().__init__(message, 'cache_error')
        self.cache_key = cache_key

class CacheTimeoutException(CacheException):
    """Cache timeout exception"""
    
    def __init__(self, message="Cache operation timeout", cache_key=None):
        super().__init__(message, cache_key)

class CacheConnectionException(CacheException):
    """Cache connection exception"""
    
    def __init__(self, message="Cache connection failed", cache_key=None):
        super().__init__(message, cache_key)

# ============================================================================
# TASK EXCEPTIONS
# ============================================================================

class TaskException(AdNetworksBaseException):
    """Task related exception"""
    
    def __init__(self, message, task_id=None, task_name=None):
        super().__init__(message, 'task_error')
        self.task_id = task_id
        self.task_name = task_name

class TaskTimeoutException(TaskException):
    """Task timeout exception"""
    
    def __init__(self, message="Task execution timeout", task_id=None, task_name=None):
        super().__init__(message, task_id, task_name)

class TaskRetryException(TaskException):
    """Task retry exception"""
    
    def __init__(self, message="Task retry limit exceeded", task_id=None, task_name=None):
        super().__init__(message, task_id, task_name)

# ============================================================================
# WEBHOOK EXCEPTIONS
# ============================================================================

class WebhookException(AdNetworksBaseException):
    """Webhook related exception"""
    
    def __init__(self, message, webhook_id=None, url=None):
        super().__init__(message, 'webhook_error')
        self.webhook_id = webhook_id
        self.url = url

class WebhookTimeoutException(WebhookException):
    """Webhook timeout exception"""
    
    def __init__(self, message="Webhook delivery timeout", webhook_id=None, url=None):
        super().__init__(message, webhook_id, url)

class WebhookDeliveryException(WebhookException):
    """Webhook delivery exception"""
    
    def __init__(self, message="Webhook delivery failed", webhook_id=None, url=None):
        super().__init__(message, webhook_id, url)

# ============================================================================
# API EXCEPTIONS
# ============================================================================

class AdNetworksAPIException(APIException):
    """Base API exception for Ad Networks"""
    
    def __init__(self, detail, code=None, status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)

class AuthenticationException(AdNetworksAPIException):
    """Authentication exception"""
    
    def __init__(self, detail="Authentication failed"):
        super().__init__(detail, 'authentication_error', status.HTTP_401_UNAUTHORIZED)

class AuthorizationException(AdNetworksAPIException):
    """Authorization exception"""
    
    def __init__(self, detail="Access denied"):
        super().__init__(detail, 'authorization_error', status.HTTP_403_FORBIDDEN)

class ResourceNotFoundException(AdNetworksAPIException):
    """Resource not found exception"""
    
    def __init__(self, detail="Resource not found"):
        super().__init__(detail, 'not_found', status.HTTP_404_NOT_FOUND)

class RateLimitException(AdNetworksAPIException):
    """Rate limit exception"""
    
    def __init__(self, detail="Rate limit exceeded"):
        super().__init__(detail, 'rate_limit_exceeded', status.HTTP_429_TOO_MANY_REQUESTS)

class ServiceUnavailableException(AdNetworksAPIException):
    """Service unavailable exception"""
    
    def __init__(self, detail="Service temporarily unavailable"):
        super().__init__(detail, 'service_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)

# ============================================================================
# SYSTEM EXCEPTIONS
# ============================================================================

class SystemException(AdNetworksBaseException):
    """System level exception"""
    
    def __init__(self, message, component=None):
        super().__init__(message, 'system_error')
        self.component = component

class DatabaseException(SystemException):
    """Database exception"""
    
    def __init__(self, message="Database error", component='database'):
        super().__init__(message, component)

class ConfigurationException(SystemException):
    """Configuration exception"""
    
    def __init__(self, message="Configuration error", component='config'):
        super().__init__(message, component)

class MaintenanceException(SystemException):
    """Maintenance exception"""
    
    def __init__(self, message="System under maintenance", component='maintenance'):
        super().__init__(message, component)

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

class ExceptionHandler:
    """Centralized exception handler"""
    
    @staticmethod
    def handle_exception(exception, context=None):
        """Handle exception and return appropriate response"""
        logger.error(f"Exception occurred: {str(exception)}", exc_info=True)
        
        if isinstance(exception, AdNetworksAPIException):
            return {
                'error': exception.detail,
                'code': exception.code,
                'status_code': exception.status_code
            }
        
        elif isinstance(exception, ValidationException):
            return {
                'error': exception.message,
                'code': exception.code,
                'field': exception.field,
                'status_code': status.HTTP_400_BAD_REQUEST
            }
        
        elif isinstance(exception, AuthenticationException):
            return {
                'error': exception.message,
                'code': exception.code,
                'status_code': status.HTTP_401_UNAUTHORIZED
            }
        
        elif isinstance(exception, (TenantNotFoundException, ResourceNotFoundException)):
            return {
                'error': exception.message,
                'code': exception.code,
                'status_code': status.HTTP_404_NOT_FOUND
            }
        
        elif isinstance(exception, (AuthorizationException, TenantSuspendedException)):
            return {
                'error': exception.message,
                'code': exception.code,
                'status_code': status.HTTP_403_FORBIDDEN
            }
        
        elif isinstance(exception, RateLimitException):
            return {
                'error': exception.message,
                'code': exception.code,
                'status_code': status.HTTP_429_TOO_MANY_REQUESTS
            }
        
        elif isinstance(exception, (ServiceUnavailableException, MaintenanceException)):
            return {
                'error': exception.message,
                'code': exception.code,
                'status_code': status.HTTP_503_SERVICE_UNAVAILABLE
            }
        
        else:
            return {
                'error': 'Internal server error',
                'code': 'internal_error',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
            }
    
    @staticmethod
    def log_exception(exception, context=None):
        """Log exception with context"""
        logger.error(
            f"Exception: {type(exception).__name__}: {str(exception)}",
            extra={
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'context': context or {}
            },
            exc_info=True
        )

# ============================================================================
# EXPORT EXCEPTIONS
# ============================================================================

__all__ = [
    # Base exceptions
    'AdNetworksBaseException',
    
    # Validation exceptions
    'ValidationException',
    'FileUploadException',
    'SecurityValidationException',
    
    # Business logic exceptions
    'OfferException',
    'OfferNotAvailableException',
    'OfferExpiredException',
    'InsufficientRewardException',
    'UserEngagementException',
    'EngagementAlreadyCompletedException',
    'DailyLimitExceededException',
    
    # Conversion exceptions
    'ConversionException',
    'ConversionValidationException',
    'ConversionAlreadyProcessedException',
    
    # Payment exceptions
    'PaymentException',
    'InsufficientFundsException',
    'PaymentProcessingException',
    'PaymentTimeoutException',
    
    # Fraud detection exceptions
    'FraudDetectionException',
    'HighFraudScoreException',
    'SuspiciousActivityException',
    'IPBlacklistedException',
    
    # Network exceptions
    'NetworkException',
    'NetworkConnectivityException',
    'NetworkTimeoutException',
    'NetworkAPIException',
    
    # Tenant exceptions
    'TenantException',
    'TenantNotFoundException',
    'TenantSuspendedException',
    'TenantLimitExceededException',
    
    # Cache exceptions
    'CacheException',
    'CacheTimeoutException',
    'CacheConnectionException',
    
    # Task exceptions
    'TaskException',
    'TaskTimeoutException',
    'TaskRetryException',
    
    # Webhook exceptions
    'WebhookException',
    'WebhookTimeoutException',
    'WebhookDeliveryException',
    
    # API exceptions
    'AdNetworksAPIException',
    'AuthenticationException',
    'AuthorizationException',
    'ResourceNotFoundException',
    'RateLimitException',
    'ServiceUnavailableException',
    
    # System exceptions
    'SystemException',
    'DatabaseException',
    'ConfigurationException',
    'MaintenanceException',
    
    # Exception handler
    'ExceptionHandler',
]

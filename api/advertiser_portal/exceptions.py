"""
Custom Exceptions for Advertiser Portal

This module contains custom exception classes for handling
specific error scenarios throughout the application.
"""

from typing import Optional, Dict, Any, List
from .enums import *


class BaseAdvertiserPortalException(Exception):
    """Base exception for all Advertiser Portal errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class ValidationError(BaseAdvertiserPortalException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 value: Optional[Any] = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
        self.value = value
        if field:
            self.details['field'] = field
        if value is not None:
            self.details['value'] = str(value)


class AuthenticationError(BaseAdvertiserPortalException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(BaseAdvertiserPortalException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Access denied", required_permission: Optional[str] = None):
        super().__init__(message, "AUTHORIZATION_ERROR")
        if required_permission:
            self.details['required_permission'] = required_permission


class NotFoundError(BaseAdvertiserPortalException):
    """Raised when requested resource is not found."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, 
                 resource_id: Optional[str] = None):
        super().__init__(message, "NOT_FOUND_ERROR")
        if resource_type:
            self.details['resource_type'] = resource_type
        if resource_id:
            self.details['resource_id'] = resource_id


class ConflictError(BaseAdvertiserPortalException):
    """Raised when resource conflict occurs."""
    
    def __init__(self, message: str, conflict_type: Optional[str] = None):
        super().__init__(message, "CONFLICT_ERROR")
        if conflict_type:
            self.details['conflict_type'] = conflict_type


class RateLimitError(BaseAdvertiserPortalException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", limit: Optional[int] = None,
                 reset_time: Optional[int] = None):
        super().__init__(message, "RATE_LIMIT_ERROR")
        if limit:
            self.details['limit'] = limit
        if reset_time:
            self.details['reset_time'] = reset_time


class PaymentError(BaseAdvertiserPortalException):
    """Raised when payment processing fails."""
    
    def __init__(self, message: str, payment_id: Optional[str] = None,
                 gateway_error: Optional[str] = None):
        super().__init__(message, "PAYMENT_ERROR")
        if payment_id:
            self.details['payment_id'] = payment_id
        if gateway_error:
            self.details['gateway_error'] = gateway_error


class IntegrationError(BaseAdvertiserPortalException):
    """Raised when third-party integration fails."""
    
    def __init__(self, message: str, integration: Optional[str] = None,
                 api_error: Optional[str] = None):
        super().__init__(message, "INTEGRATION_ERROR")
        if integration:
            self.details['integration'] = integration
        if api_error:
            self.details['api_error'] = api_error


class CacheError(BaseAdvertiserPortalException):
    """Raised when cache operation fails."""
    
    def __init__(self, message: str, cache_key: Optional[str] = None):
        super().__init__(message, "CACHE_ERROR")
        if cache_key:
            self.details['cache_key'] = cache_key


class DatabaseError(BaseAdvertiserPortalException):
    """Raised when database operation fails."""
    
    def __init__(self, message: str, query: Optional[str] = None):
        super().__init__(message, "DATABASE_ERROR")
        if query:
            self.details['query'] = query


class FileProcessingError(BaseAdvertiserPortalException):
    """Raised when file processing fails."""
    
    def __init__(self, message: str, file_name: Optional[str] = None,
                 file_type: Optional[str] = None):
        super().__init__(message, "FILE_PROCESSING_ERROR")
        if file_name:
            self.details['file_name'] = file_name
        if file_type:
            self.details['file_type'] = file_type


class APIError(BaseAdvertiserPortalException):
    """Raised when API request fails."""
    
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message, "API_ERROR")
        if status_code:
            self.details['status_code'] = status_code
        if response_data:
            self.details['response_data'] = response_data


# Advertiser-specific exceptions
class AdvertiserError(BaseAdvertiserPortalException):
    """Base exception for advertiser-related errors."""
    pass


class AdvertiserNotFoundError(NotFoundError, AdvertiserError):
    """Raised when advertiser is not found."""
    
    def __init__(self, advertiser_id: str):
        super().__init__(f"Advertiser not found: {advertiser_id}", 
                        resource_type="advertiser", resource_id=advertiser_id)


class AdvertiserValidationError(ValidationError, AdvertiserError):
    """Raised when advertiser data validation fails."""
    pass


class AdvertiserCreationError(AdvertiserError):
    """Raised when advertiser creation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "ADVERTISER_CREATION_ERROR")


class AdvertiserUpdateError(AdvertiserError):
    """Raised when advertiser update fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "ADVERTISER_UPDATE_ERROR")


class AdvertiserDeletionError(AdvertiserError):
    """Raised when advertiser deletion fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "ADVERTISER_DELETION_ERROR")


class AdvertiserVerificationError(AdvertiserError):
    """Raised when advertiser verification fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "ADVERTISER_VERIFICATION_ERROR")


class AdvertiserSuspensionError(AdvertiserError):
    """Raised when advertiser suspension fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "ADVERTISER_SUSPENSION_ERROR")


# Campaign-specific exceptions
class CampaignError(BaseAdvertiserPortalException):
    """Base exception for campaign-related errors."""
    pass


class CampaignNotFoundError(NotFoundError, CampaignError):
    """Raised when campaign is not found."""
    
    def __init__(self, campaign_id: str):
        super().__init__(f"Campaign not found: {campaign_id}", 
                        resource_type="campaign", resource_id=campaign_id)


class CampaignValidationError(ValidationError, CampaignError):
    """Raised when campaign data validation fails."""
    pass


class CampaignCreationError(CampaignError):
    """Raised when campaign creation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_CREATION_ERROR")


class CampaignUpdateError(CampaignError):
    """Raised when campaign update fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_UPDATE_ERROR")


class CampaignDeletionError(CampaignError):
    """Raised when campaign deletion fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_DELETION_ERROR")


class CampaignActivationError(CampaignError):
    """Raised when campaign activation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_ACTIVATION_ERROR")


class CampaignBudgetError(CampaignError):
    """Raised when campaign budget operation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_BUDGET_ERROR")


class CampaignDuplicationError(CampaignError):
    """Raised when campaign duplication fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CAMPAIGN_DUPLICATION_ERROR")


# Creative-specific exceptions
class CreativeError(BaseAdvertiserPortalException):
    """Base exception for creative-related errors."""
    pass


class CreativeNotFoundError(NotFoundError, CreativeError):
    """Raised when creative is not found."""
    
    def __init__(self, creative_id: str):
        super().__init__(f"Creative not found: {creative_id}", 
                        resource_type="creative", resource_id=creative_id)


class CreativeValidationError(ValidationError, CreativeError):
    """Raised when creative data validation fails."""
    pass


class CreativeUploadError(CreativeError):
    """Raised when creative upload fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CREATIVE_UPLOAD_ERROR")


class CreativeProcessingError(CreativeError):
    """Raised when creative processing fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CREATIVE_PROCESSING_ERROR")


class CreativeApprovalError(CreativeError):
    """Raised when creative approval fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "CREATIVE_APPROVAL_ERROR")


class CreativeSizeError(CreativeError):
    """Raised when creative size exceeds limits."""
    
    def __init__(self, message: str, actual_size: Optional[int] = None,
                 max_size: Optional[int] = None):
        super().__init__(message, "CREATIVE_SIZE_ERROR")
        if actual_size:
            self.details['actual_size'] = actual_size
        if max_size:
            self.details['max_size'] = max_size


class CreativeFormatError(CreativeError):
    """Raised when creative format is not supported."""
    
    def __init__(self, message: str, format_type: Optional[str] = None):
        super().__init__(message, "CREATIVE_FORMAT_ERROR")
        if format_type:
            self.details['format_type'] = format_type


# Targeting-specific exceptions
class TargetingError(BaseAdvertiserPortalException):
    """Base exception for targeting-related errors."""
    pass


class TargetingNotFoundError(NotFoundError, TargetingError):
    """Raised when targeting configuration is not found."""
    
    def __init__(self, targeting_id: str):
        super().__init__(f"Targeting configuration not found: {targeting_id}", 
                        resource_type="targeting", resource_id=targeting_id)


class TargetingValidationError(ValidationError, TargetingError):
    """Raised when targeting data validation fails."""
    pass


class TargetingCreationError(TargetingError):
    """Raised when targeting creation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "TARGETING_CREATION_ERROR")


class TargetingUpdateError(TargetingError):
    """Raised when targeting update fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "TARGETING_UPDATE_ERROR")


class AudienceSizeError(TargetingError):
    """Raised when audience size is invalid."""
    
    def __init__(self, message: str, estimated_size: Optional[int] = None):
        super().__init__(message, "AUDIENCE_SIZE_ERROR")
        if estimated_size:
            self.details['estimated_size'] = estimated_size


# Analytics-specific exceptions
class AnalyticsError(BaseAdvertiserPortalException):
    """Base exception for analytics-related errors."""
    pass


class AnalyticsDataError(AnalyticsError):
    """Raised when analytics data processing fails."""
    
    def __init__(self, message: str, metric: Optional[str] = None):
        super().__init__(message, "ANALYTICS_DATA_ERROR")
        if metric:
            self.details['metric'] = metric


class AnalyticsQueryError(AnalyticsError):
    """Raised when analytics query fails."""
    
    def __init__(self, message: str, query: Optional[str] = None):
        super().__init__(message, "ANALYTICS_QUERY_ERROR")
        if query:
            self.details['query'] = query


class AnalyticsReportError(AnalyticsError):
    """Raised when analytics report generation fails."""
    
    def __init__(self, message: str, report_type: Optional[str] = None):
        super().__init__(message, "ANALYTICS_REPORT_ERROR")
        if report_type:
            self.details['report_type'] = report_type


class StatisticalSignificanceError(AnalyticsError):
    """Raised when statistical significance test fails."""
    
    def __init__(self, message: str, sample_size: Optional[int] = None):
        super().__init__(message, "STATISTICAL_SIGNIFICANCE_ERROR")
        if sample_size:
            self.details['sample_size'] = sample_size


# Billing-specific exceptions
class BillingError(BaseAdvertiserPortalException):
    """Base exception for billing-related errors."""
    pass


class BillingValidationError(ValidationError, BillingError):
    """Raised when billing data validation fails."""
    pass


class InvoiceError(BillingError):
    """Raised when invoice operation fails."""
    
    def __init__(self, message: str, invoice_number: Optional[str] = None):
        super().__init__(message, "INVOICE_ERROR")
        if invoice_number:
            self.details['invoice_number'] = invoice_number


class PaymentProcessingError(PaymentError, BillingError):
    """Raised when payment processing fails."""
    pass


class InsufficientFundsError(BillingError):
    """Raised when insufficient funds for operation."""
    
    def __init__(self, message: str, required_amount: Optional[float] = None,
                 available_amount: Optional[float] = None):
        super().__init__(message, "INSUFFICIENT_FUNDS_ERROR")
        if required_amount:
            self.details['required_amount'] = required_amount
        if available_amount:
            self.details['available_amount'] = available_amount


class CreditLimitError(BillingError):
    """Raised when credit limit is exceeded."""
    
    def __init__(self, message: str, credit_limit: Optional[float] = None,
                 current_usage: Optional[float] = None):
        super().__init__(message, "CREDIT_LIMIT_ERROR")
        if credit_limit:
            self.details['credit_limit'] = credit_limit
        if current_usage:
            self.details['current_usage'] = current_usage


# Fraud detection-specific exceptions
class FraudDetectionError(BaseAdvertiserPortalException):
    """Base exception for fraud detection errors."""
    pass


class FraudAnalysisError(FraudDetectionError):
    """Raised when fraud analysis fails."""
    
    def __init__(self, message: str, fraud_type: Optional[str] = None):
        super().__init__(message, "FRAUD_ANALYSIS_ERROR")
        if fraud_type:
            self.details['fraud_type'] = fraud_type


class FraudBlockingError(FraudDetectionError):
    """Raised when fraud blocking fails."""
    
    def __init__(self, message: str, reason: Optional[str] = None):
        super().__init__(message, "FRAUD_BLOCKING_ERROR")
        if reason:
            self.details['reason'] = reason


class SuspiciousActivityError(FraudDetectionError):
    """Raised when suspicious activity is detected."""
    
    def __init__(self, message: str, activity_type: Optional[str] = None,
                 risk_score: Optional[int] = None):
        super().__init__(message, "SUSPICIOUS_ACTIVITY_ERROR")
        if activity_type:
            self.details['activity_type'] = activity_type
        if risk_score:
            self.details['risk_score'] = risk_score


# A/B testing-specific exceptions
class ABTestingError(BaseAdvertiserPortalException):
    """Base exception for A/B testing errors."""
    pass


class TestCreationError(ABTestingError):
    """Raised when A/B test creation fails."""
    
    def __init__(self, message: str, test_type: Optional[str] = None):
        super().__init__(message, "TEST_CREATION_ERROR")
        if test_type:
            self.details['test_type'] = test_type


class TestExecutionError(ABTestingError):
    """Raised when A/B test execution fails."""
    
    def __init__(self, message: str, test_id: Optional[str] = None):
        super().__init__(message, "TEST_EXECUTION_ERROR")
        if test_id:
            self.details['test_id'] = test_id


class TestAnalysisError(ABTestingError):
    """Raised when A/B test analysis fails."""
    
    def __init__(self, message: str, analysis_type: Optional[str] = None):
        super().__init__(message, "TEST_ANALYSIS_ERROR")
        if analysis_type:
            self.details['analysis_type'] = analysis_type


class InsufficientSampleSizeError(ABTestingError):
    """Raised when sample size is insufficient for analysis."""
    
    def __init__(self, message: str, current_size: Optional[int] = None,
                 required_size: Optional[int] = None):
        super().__init__(message, "INSUFFICIENT_SAMPLE_SIZE_ERROR")
        if current_size:
            self.details['current_size'] = current_size
        if required_size:
            self.details['required_size'] = required_size


# Integration-specific exceptions
class IntegrationConnectionError(IntegrationError):
    """Raised when integration connection fails."""
    
    def __init__(self, message: str, integration_type: Optional[str] = None):
        super().__init__(message, "INTEGRATION_CONNECTION_ERROR")
        if integration_type:
            self.details['integration_type'] = integration_type


class IntegrationConfigurationError(IntegrationError):
    """Raised when integration configuration is invalid."""
    
    def __init__(self, message: str, config_field: Optional[str] = None):
        super().__init__(message, "INTEGRATION_CONFIGURATION_ERROR")
        if config_field:
            self.details['config_field'] = config_field


class IntegrationRateLimitError(IntegrationError):
    """Raised when integration rate limit is exceeded."""
    
    def __init__(self, message: str, limit: Optional[int] = None,
                 reset_time: Optional[int] = None):
        super().__init__(message, "INTEGRATION_RATE_LIMIT_ERROR")
        if limit:
            self.details['limit'] = limit
        if reset_time:
            self.details['reset_time'] = reset_time


# Task and queue-specific exceptions
class TaskError(BaseAdvertiserPortalException):
    """Base exception for task-related errors."""
    pass


class TaskExecutionError(TaskError):
    """Raised when task execution fails."""
    
    def __init__(self, message: str, task_id: Optional[str] = None,
                 task_type: Optional[str] = None):
        super().__init__(message, "TASK_EXECUTION_ERROR")
        if task_id:
            self.details['task_id'] = task_id
        if task_type:
            self.details['task_type'] = task_type


class TaskTimeoutError(TaskError):
    """Raised when task times out."""
    
    def __init__(self, message: str, timeout_duration: Optional[int] = None):
        super().__init__(message, "TASK_TIMEOUT_ERROR")
        if timeout_duration:
            self.details['timeout_duration'] = timeout_duration


class QueueError(BaseAdvertiserPortalException):
    """Base exception for queue-related errors."""
    pass


class QueueFullError(QueueError):
    """Raised when queue is full."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None,
                 queue_size: Optional[int] = None):
        super().__init__(message, "QUEUE_FULL_ERROR")
        if queue_name:
            self.details['queue_name'] = queue_name
        if queue_size:
            self.details['queue_size'] = queue_size


class QueueConnectionError(QueueError):
    """Raised when queue connection fails."""
    
    def __init__(self, message: str, queue_name: Optional[str] = None):
        super().__init__(message, "QUEUE_CONNECTION_ERROR")
        if queue_name:
            self.details['queue_name'] = queue_name


# Configuration-specific exceptions
class ConfigurationError(BaseAdvertiserPortalException):
    """Base exception for configuration errors."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, "INVALID_CONFIGURATION_ERROR")
        if config_key:
            self.details['config_key'] = config_key


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, "MISSING_CONFIGURATION_ERROR")
        if config_key:
            self.details['config_key'] = config_key


# Webhook-specific exceptions
class WebhookError(BaseAdvertiserPortalException):
    """Base exception for webhook errors."""
    pass


class WebhookDeliveryError(WebhookError):
    """Raised when webhook delivery fails."""
    
    def __init__(self, message: str, webhook_url: Optional[str] = None,
                 status_code: Optional[int] = None):
        super().__init__(message, "WEBHOOK_DELIVERY_ERROR")
        if webhook_url:
            self.details['webhook_url'] = webhook_url
        if status_code:
            self.details['status_code'] = status_code


class WebhookValidationError(WebhookError):
    """Raised when webhook validation fails."""
    
    def __init__(self, message: str, validation_error: Optional[str] = None):
        super().__init__(message, "WEBHOOK_VALIDATION_ERROR")
        if validation_error:
            self.details['validation_error'] = validation_error


# Additional Exceptions for Main Models
class OfferError(BaseAdvertiserPortalException):
    """Raised when offer operations fail."""
    
    def __init__(self, message: str, offer_id: Optional[str] = None):
        super().__init__(message, "OFFER_ERROR")
        if offer_id:
            self.details['offer_id'] = offer_id


class OfferNotFoundError(NotFoundError):
    """Raised when an offer is not found."""
    
    def __init__(self, offer_id: str):
        super().__init__(f"Offer with ID '{offer_id}' not found")
        self.details['offer_id'] = offer_id


class OfferValidationError(ValidationError):
    """Raised when offer validation fails."""
    
    def __init__(self, message: str, offer_field: Optional[str] = None):
        super().__init__(message, field=offer_field)
        self.error_code = "OFFER_VALIDATION_ERROR"


class CampaignError(BaseAdvertiserPortalException):
    """Raised when campaign operations fail."""
    
    def __init__(self, message: str, campaign_id: Optional[str] = None):
        super().__init__(message, "CAMPAIGN_ERROR")
        if campaign_id:
            self.details['campaign_id'] = campaign_id


class CampaignNotFoundError(NotFoundError):
    """Raised when a campaign is not found."""
    
    def __init__(self, campaign_id: str):
        super().__init__(f"Campaign with ID '{campaign_id}' not found")
        self.details['campaign_id'] = campaign_id


class CampaignValidationError(ValidationError):
    """Raised when campaign validation fails."""
    
    def __init__(self, message: str, campaign_field: Optional[str] = None):
        super().__init__(message, field=campaign_field)
        self.error_code = "CAMPAIGN_VALIDATION_ERROR"


class BudgetExceededError(BaseAdvertiserPortalException):
    """Raised when budget limits are exceeded."""
    
    def __init__(self, message: str, budget_type: Optional[str] = None, current_amount: Optional[float] = None):
        super().__init__(message, "BUDGET_EXCEEDED")
        if budget_type:
            self.details['budget_type'] = budget_type
        if current_amount is not None:
            self.details['current_amount'] = current_amount


class TrackingError(BaseAdvertiserPortalException):
    """Raised when tracking operations fail."""
    
    def __init__(self, message: str, tracking_id: Optional[str] = None):
        super().__init__(message, "TRACKING_ERROR")
        if tracking_id:
            self.details['tracking_id'] = tracking_id


class TrackingPixelError(TrackingError):
    """Raised when tracking pixel operations fail."""
    
    def __init__(self, message: str, pixel_id: Optional[str] = None):
        super().__init__(message, pixel_id)
        self.error_code = "TRACKING_PIXEL_ERROR"


class ConversionError(TrackingError):
    """Raised when conversion operations fail."""
    
    def __init__(self, message: str, conversion_id: Optional[str] = None):
        super().__init__(message, conversion_id)
        self.error_code = "CONVERSION_ERROR"


class ConversionValidationError(ValidationError):
    """Raised when conversion validation fails."""
    
    def __init__(self, message: str, conversion_field: Optional[str] = None):
        super().__init__(message, field=conversion_field)
        self.error_code = "CONVERSION_VALIDATION_ERROR"


class BillingError(BaseAdvertiserPortalException):
    """Raised when billing operations fail."""
    
    def __init__(self, message: str, billing_id: Optional[str] = None):
        super().__init__(message, "BILLING_ERROR")
        if billing_id:
            self.details['billing_id'] = billing_id


class WalletError(BillingError):
    """Raised when wallet operations fail."""
    
    def __init__(self, message: str, wallet_id: Optional[str] = None):
        super().__init__(message, wallet_id)
        self.error_code = "WALLET_ERROR"


class InsufficientFundsError(BillingError):
    """Raised when insufficient funds are available."""
    
    def __init__(self, message: str, available_balance: Optional[float] = None, required_amount: Optional[float] = None):
        super().__init__(message, "INSUFFICIENT_FUNDS")
        if available_balance is not None:
            self.details['available_balance'] = available_balance
        if required_amount is not None:
            self.details['required_amount'] = required_amount


class TransactionError(BillingError):
    """Raised when transaction operations fail."""
    
    def __init__(self, message: str, transaction_id: Optional[str] = None):
        super().__init__(message, transaction_id)
        self.error_code = "TRANSACTION_ERROR"


class InvoiceError(BillingError):
    """Raised when invoice operations fail."""
    
    def __init__(self, message: str, invoice_id: Optional[str] = None):
        super().__init__(message, invoice_id)
        self.error_code = "INVOICE_ERROR"


class FraudDetectionError(BaseAdvertiserPortalException):
    """Raised when fraud detection operations fail."""
    
    def __init__(self, message: str, fraud_type: Optional[str] = None):
        super().__init__(message, "FRAUD_DETECTION_ERROR")
        if fraud_type:
            self.details['fraud_type'] = fraud_type


class FraudScoreError(FraudDetectionError):
    """Raised when fraud score calculation fails."""
    
    def __init__(self, message: str, score_type: Optional[str] = None):
        super().__init__(message, "fraud_score")
        self.error_code = "FRAUD_SCORE_ERROR"
        if score_type:
            self.details['score_type'] = score_type


class FraudConfigError(FraudDetectionError):
    """Raised when fraud configuration operations fail."""
    
    def __init__(self, message: str, config_name: Optional[str] = None):
        super().__init__(message, "fraud_config")
        self.error_code = "FRAUD_CONFIG_ERROR"
        if config_name:
            self.details['config_name'] = config_name


class NotificationError(BaseAdvertiserPortalException):
    """Raised when notification operations fail."""
    
    def __init__(self, message: str, notification_id: Optional[str] = None):
        super().__init__(message, "NOTIFICATION_ERROR")
        if notification_id:
            self.details['notification_id'] = notification_id


class EmailNotificationError(NotificationError):
    """Raised when email notification fails."""
    
    def __init__(self, message: str, recipient: Optional[str] = None):
        super().__init__(message, "email_notification")
        self.error_code = "EMAIL_NOTIFICATION_ERROR"
        if recipient:
            self.details['recipient'] = recipient


class SMSNotificationError(NotificationError):
    """Raised when SMS notification fails."""
    
    def __init__(self, message: str, phone_number: Optional[str] = None):
        super().__init__(message, "sms_notification")
        self.error_code = "SMS_NOTIFICATION_ERROR"
        if phone_number:
            self.details['phone_number'] = phone_number


class PushNotificationError(NotificationError):
    """Raised when push notification fails."""
    
    def __init__(self, message: str, device_id: Optional[str] = None):
        super().__init__(message, "push_notification")
        self.error_code = "PUSH_NOTIFICATION_ERROR"
        if device_id:
            self.details['device_id'] = device_id


class ReportError(BaseAdvertiserPortalException):
    """Raised when report operations fail."""
    
    def __init__(self, message: str, report_id: Optional[str] = None):
        super().__init__(message, "REPORT_ERROR")
        if report_id:
            self.details['report_id'] = report_id


class ReportGenerationError(ReportError):
    """Raised when report generation fails."""
    
    def __init__(self, message: str, report_type: Optional[str] = None):
        super().__init__(message, "report_generation")
        self.error_code = "REPORT_GENERATION_ERROR"
        if report_type:
            self.details['report_type'] = report_type


class ReportValidationError(ValidationError):
    """Raised when report validation fails."""
    
    def __init__(self, message: str, report_field: Optional[str] = None):
        super().__init__(message, field=report_field)
        self.error_code = "REPORT_VALIDATION_ERROR"


class MLError(BaseAdvertiserPortalException):
    """Raised when ML operations fail."""
    
    def __init__(self, message: str, model_id: Optional[str] = None):
        super().__init__(message, "ML_ERROR")
        if model_id:
            self.details['model_id'] = model_id


class ModelTrainingError(MLError):
    """Raised when ML model training fails."""
    
    def __init__(self, message: str, model_name: Optional[str] = None):
        super().__init__(message, "model_training")
        self.error_code = "MODEL_TRAINING_ERROR"
        if model_name:
            self.details['model_name'] = model_name


class PredictionError(MLError):
    """Raised when ML prediction fails."""
    
    def __init__(self, message: str, model_id: Optional[str] = None):
        super().__init__(message, "prediction")
        self.error_code = "PREDICTION_ERROR"
        if model_id:
            self.details['model_id'] = model_id


class ModelValidationError(ValidationError):
    """Raised when ML model validation fails."""
    
    def __init__(self, message: str, model_field: Optional[str] = None):
        super().__init__(message, field=model_field)
        self.error_code = "MODEL_VALIDATION_ERROR"


class CreativeError(BaseAdvertiserPortalException):
    """Raised when creative operations fail."""
    
    def __init__(self, message: str, creative_id: Optional[str] = None):
        super().__init__(message, "CREATIVE_ERROR")
        if creative_id:
            self.details['creative_id'] = creative_id


class CreativeValidationError(ValidationError):
    """Raised when creative validation fails."""
    
    def __init__(self, message: str, creative_field: Optional[str] = None):
        super().__init__(message, field=creative_field)
        self.error_code = "CREATIVE_VALIDATION_ERROR"


class TargetingError(BaseAdvertiserPortalException):
    """Raised when targeting operations fail."""
    
    def __init__(self, message: str, targeting_id: Optional[str] = None):
        super().__init__(message, "TARGETING_ERROR")
        if targeting_id:
            self.details['targeting_id'] = targeting_id


class TargetingValidationError(ValidationError):
    """Raised when targeting validation fails."""
    
    def __init__(self, message: str, targeting_field: Optional[str] = None):
        super().__init__(message, field=targeting_field)
        self.error_code = "TARGETING_VALIDATION_ERROR"


class APIError(BaseAdvertiserPortalException):
    """Raised when API operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message, "API_ERROR")
        if status_code:
            self.details['status_code'] = status_code
        if response_data:
            self.details['response_data'] = response_data


class RateLimitError(BaseAdvertiserPortalException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, limit: Optional[int] = None, window: Optional[int] = None):
        super().__init__(message, "RATE_LIMIT_ERROR")
        if limit:
            self.details['limit'] = limit
        if window:
            self.details['window'] = window


class ConfigurationError(BaseAdvertiserPortalException):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, "CONFIGURATION_ERROR")
        if config_key:
            self.details['config_key'] = config_key


class ServiceUnavailableError(BaseAdvertiserPortalException):
    """Raised when a service is unavailable."""
    
    def __init__(self, message: str, service_name: Optional[str] = None):
        super().__init__(message, "SERVICE_UNAVAILABLE")
        if service_name:
            self.details['service_name'] = service_name


# Exception handler utilities
class ExceptionHandler:
    """Utility class for handling exceptions."""
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str) -> BaseAdvertiserPortalException:
        """Handle database errors and convert to appropriate exception."""
        error_message = f"Database operation '{operation}' failed: {str(error)}"
        
        if "duplicate key" in str(error).lower():
            return ConflictError(error_message, conflict_type="duplicate_entry")
        elif "foreign key" in str(error).lower():
            return ValidationError(error_message)
        elif "connection" in str(error).lower():
            return DatabaseError(error_message)
        else:
            return DatabaseError(error_message)
    
    @staticmethod
    def handle_api_error(response: Any, operation: str) -> APIError:
        """Handle API errors and convert to appropriate exception."""
        status_code = getattr(response, 'status_code', None)
        response_data = getattr(response, 'json', lambda: {})()
        
        message = f"API operation '{operation}' failed"
        if status_code:
            message += f" with status {status_code}"
        
        return APIError(message, status_code=status_code, response_data=response_data)
    
    @staticmethod
    def get_error_response(exception: BaseAdvertiserPortalException) -> Dict[str, Any]:
        """Get standardized error response for API."""
        response = exception.to_dict()
        response['status'] = 'error'
        
        # Add HTTP status code based on exception type
        if isinstance(exception, (AuthenticationError, AuthorizationError)):
            response['http_status'] = 401 if isinstance(exception, AuthenticationError) else 403
        elif isinstance(exception, NotFoundError):
            response['http_status'] = 404
        elif isinstance(exception, (ValidationError, ConflictError)):
            response['http_status'] = 400
        elif isinstance(exception, RateLimitError):
            response['http_status'] = 429
        elif isinstance(exception, PaymentError):
            response['http_status'] = 402
        else:
            response['http_status'] = 500
        
        return response

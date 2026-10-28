"""
Alert System Exceptions
This file contains custom exceptions for the alert system.
"""

from rest_framework.exceptions import APIException
from rest_framework import status


class AlertSystemException(Exception):
    """Base exception for all alert system errors"""
    default_message = "An error occurred in the alert system"
    default_code = "alert_system_error"
    
    def __init__(self, message=None, code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)


# Validation Exceptions
class ValidationError(AlertSystemException):
    """Validation error"""
    default_message = "Validation error"
    default_code = "validation_error"


class InvalidThresholdError(ValidationError):
    """Invalid threshold value"""
    default_message = "Invalid threshold value"
    default_code = "invalid_threshold"


class InvalidTimeWindowError(ValidationError):
    """Invalid time window"""
    default_message = "Invalid time window"
    default_code = "invalid_time_window"


class InvalidRecipientError(ValidationError):
    """Invalid recipient"""
    default_message = "Invalid recipient format"
    default_code = "invalid_recipient"


# Alert Processing Exceptions
class AlertProcessingError(AlertSystemException):
    """Error during alert processing"""
    default_message = "Error processing alert"
    default_code = "alert_processing_error"


class AlertRuleNotFoundError(AlertProcessingError):
    """Alert rule not found"""
    default_message = "Alert rule not found"
    default_code = "alert_rule_not_found"


class AlertRuleInactiveError(AlertProcessingError):
    """Alert rule is inactive"""
    default_message = "Alert rule is inactive"
    default_code = "alert_rule_inactive"


class AlertRuleCooldownError(AlertProcessingError):
    """Alert rule is in cooldown"""
    default_message = "Alert rule is in cooldown period"
    default_code = "alert_rule_cooldown"


class AlertSuppressionError(AlertProcessingError):
    """Alert suppression error"""
    default_message = "Alert suppressed"
    default_code = "alert_suppressed"


# Notification Exceptions
class NotificationError(AlertSystemException):
    """Notification error"""
    default_message = "Error sending notification"
    default_code = "notification_error"


class NotificationChannelError(NotificationError):
    """Notification channel error"""
    default_message = "Notification channel error"
    default_code = "notification_channel_error"


class NotificationTemplateError(NotificationError):
    """Notification template error"""
    default_message = "Notification template error"
    default_code = "notification_template_error"


class NotificationRecipientError(NotificationError):
    """Notification recipient error"""
    default_message = "Invalid notification recipient"
    default_code = "notification_recipient_error"


# Integration Exceptions
class IntegrationError(AlertSystemException):
    """Integration error"""
    default_message = "Integration error"
    default_code = "integration_error"


class SlackIntegrationError(IntegrationError):
    """Slack integration error"""
    default_message = "Slack integration error"
    default_code = "slack_integration_error"


class DiscordIntegrationError(IntegrationError):
    """Discord integration error"""
    default_message = "Discord integration error"
    default_code = "discord_integration_error"


class PagerDutyIntegrationError(IntegrationError):
    """PagerDuty integration error"""
    default_message = "PagerDuty integration error"
    default_code = "pagerduty_integration_error"


class OpsGenieIntegrationError(IntegrationError):
    """OpsGenie integration error"""
    default_message = "OpsGenie integration error"
    default_code = "opsgenie_integration_error"


class EmailIntegrationError(IntegrationError):
    """Email integration error"""
    default_message = "Email integration error"
    default_code = "email_integration_error"


class SMSIntegrationError(IntegrationError):
    """SMS integration error"""
    default_message = "SMS integration error"
    default_code = "sms_integration_error"


# Database Exceptions
class DatabaseError(AlertSystemException):
    """Database error"""
    default_message = "Database error"
    default_code = "database_error"


class DatabaseTimeoutError(DatabaseError):
    """Database timeout error"""
    default_message = "Database operation timed out"
    default_code = "database_timeout"


class DatabaseConnectionError(DatabaseError):
    """Database connection error"""
    default_message = "Database connection error"
    default_code = "database_connection_error"


# Cache Exceptions
class CacheError(AlertSystemException):
    """Cache error"""
    default_message = "Cache error"
    default_code = "cache_error"


class CacheTimeoutError(CacheError):
    """Cache timeout error"""
    default_message = "Cache operation timed out"
    default_code = "cache_timeout"


class CacheMissError(CacheError):
    """Cache miss error"""
    default_message = "Cache miss"
    default_code = "cache_miss"


# Rate Limiting Exceptions
class RateLimitError(AlertSystemException):
    """Rate limit error"""
    default_message = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"


class APIRateLimitError(RateLimitError):
    """API rate limit error"""
    default_message = "API rate limit exceeded"
    default_code = "api_rate_limit_exceeded"


class AlertRateLimitError(RateLimitError):
    """Alert rate limit error"""
    default_message = "Alert rate limit exceeded"
    default_code = "alert_rate_limit_exceeded"


class NotificationRateLimitError(NotificationError, RateLimitError):
    """Notification rate limit error"""
    default_message = "Notification rate limit exceeded"
    default_code = "notification_rate_limit_exceeded"


# Permission Exceptions
class PermissionError(AlertSystemException):
    """Permission error"""
    default_message = "Permission denied"
    default_code = "permission_denied"


class UnauthorizedAccessError(PermissionError):
    """Unauthorized access error"""
    default_message = "Unauthorized access"
    default_code = "unauthorized_access"


class InsufficientPermissionsError(PermissionError):
    """Insufficient permissions error"""
    default_message = "Insufficient permissions"
    default_code = "insufficient_permissions"


# Configuration Exceptions
class ConfigurationError(AlertSystemException):
    """Configuration error"""
    default_message = "Configuration error"
    default_code = "configuration_error"


class MissingConfigurationError(ConfigurationError):
    """Missing configuration error"""
    default_message = "Missing configuration"
    default_code = "missing_configuration"


class InvalidConfigurationError(ConfigurationError):
    """Invalid configuration error"""
    default_message = "Invalid configuration"
    default_code = "invalid_configuration"


# External Service Exceptions
class ExternalServiceError(AlertSystemException):
    """External service error"""
    default_message = "External service error"
    default_code = "external_service_error"


class ServiceUnavailableError(ExternalServiceError):
    """Service unavailable error"""
    default_message = "Service temporarily unavailable"
    default_code = "service_unavailable"


class ServiceTimeoutError(ExternalServiceError):
    """Service timeout error"""
    default_message = "Service request timed out"
    default_code = "service_timeout"


# Data Processing Exceptions
class DataProcessingError(AlertSystemException):
    """Data processing error"""
    default_message = "Data processing error"
    default_code = "data_processing_error"


class InsufficientDataError(DataProcessingError):
    """Insufficient data error"""
    default_message = "Insufficient data for analysis"
    default_code = "insufficient_data"


class DataCorruptionError(DataProcessingError):
    """Data corruption error"""
    default_message = "Data corruption detected"
    default_code = "data_corruption"


class DataFormatError(DataProcessingError):
    """Data format error"""
    default_message = "Invalid data format"
    default_code = "data_format_error"


# API Exceptions (for REST framework)
class AlertAPIException(APIException):
    """Base API exception for alert system"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred"
    default_code = "error"
    
    def __init__(self, detail=None, code=None, status_code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail, code)


class NotFoundAPIException(AlertAPIException):
    """Resource not found API exception"""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"
    default_code = "not_found"


class ValidationAPIException(AlertAPIException):
    """Validation error API exception"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Validation error"
    default_code = "validation_error"


class PermissionAPIException(AlertAPIException):
    """Permission error API exception"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Permission denied"
    default_code = "permission_denied"


class RateLimitAPIException(AlertAPIException):
    """Rate limit API exception"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"


# Utility functions
def handle_alert_exception(exception, context=None):
    """Handle alert system exceptions and return appropriate response"""
    if isinstance(exception, AlertAPIException):
        raise exception
    
    # Convert to API exception if needed
    if isinstance(exception, AlertSystemException):
        raise AlertAPIException(
            detail=exception.message,
            code=exception.code,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Re-raise unknown exceptions
    raise exception
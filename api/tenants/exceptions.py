"""
Custom Exceptions for Tenant Management System

This module contains custom exception classes for tenant management operations
including validation errors, business logic errors, and API errors.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class TenantManagementException(APIException):
    """Base exception for tenant management operations."""
    
    def __init__(self, detail, code=None, status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


class TenantNotFoundError(TenantManagementException):
    """Exception raised when a tenant is not found."""
    
    def __init__(self, tenant_id=None, message=None):
        if message:
            detail = message
        else:
            detail = f"Tenant with ID {tenant_id} not found" if tenant_id else "Tenant not found"
        super().__init__(detail, 'tenant_not_found', status.HTTP_404_NOT_FOUND)


class TenantAlreadyExistsError(TenantManagementException):
    """Exception raised when a tenant already exists."""
    
    def __init__(self, field=None, value=None):
        if field and value:
            detail = f"Tenant with {field} '{value}' already exists"
        else:
            detail = "Tenant already exists"
        super().__init__(detail, 'tenant_already_exists', status.HTTP_409_CONFLICT)


class TenantSuspendedError(TenantManagementException):
    """Exception raised when a tenant is suspended."""
    
    def __init__(self, reason=None):
        if reason:
            detail = f"Tenant is suspended: {reason}"
        else:
            detail = "Tenant is suspended"
        super().__init__(detail, 'tenant_suspended', status.HTTP_403_FORBIDDEN)


class TenantInactiveError(TenantManagementException):
    """Exception raised when a tenant is inactive."""
    
    def __init__(self):
        detail = "Tenant is inactive"
        super().__init__(detail, 'tenant_inactive', status.HTTP_403_FORBIDDEN)


class PlanNotFoundError(TenantManagementException):
    """Exception raised when a plan is not found."""
    
    def __init__(self, plan_id=None):
        if plan_id:
            detail = f"Plan with ID {plan_id} not found"
        else:
            detail = "Plan not found"
        super().__init__(detail, 'plan_not_found', status.HTTP_404_NOT_FOUND)


class PlanNotAvailableError(TenantManagementException):
    """Exception raised when a plan is not available."""
    
    def __init__(self, plan_name=None):
        if plan_name:
            detail = f"Plan '{plan_name}' is not available"
        else:
            detail = "Plan is not available"
        super().__init__(detail, 'plan_not_available', status.HTTP_400_BAD_REQUEST)


class InsufficientQuotaError(TenantManagementException):
    """Exception raised when quota is exceeded."""
    
    def __init__(self, quota_type=None, current=None, limit=None):
        if quota_type and current is not None and limit is not None:
            detail = f"Insufficient quota for {quota_type}: {current}/{limit}"
        else:
            detail = "Insufficient quota"
        super().__init__(detail, 'insufficient_quota', status.HTTP_429_TOO_MANY_REQUESTS)


class APIKeyNotFoundError(TenantManagementException):
    """Exception raised when an API key is not found."""
    
    def __init__(self, key_id=None):
        if key_id:
            detail = f"API key with ID {key_id} not found"
        else:
            detail = "API key not found"
        super().__init__(detail, 'api_key_not_found', status.HTTP_404_NOT_FOUND)


class APIKeyExpiredError(TenantManagementException):
    """Exception raised when an API key is expired."""
    
    def __init__(self):
        detail = "API key has expired"
        super().__init__(detail, 'api_key_expired', status.HTTP_401_UNAUTHORIZED)


class InvalidAPIKeyError(TenantManagementException):
    """Exception raised when an API key is invalid."""
    
    def __init__(self):
        detail = "Invalid API key"
        super().__init__(detail, 'invalid_api_key', status.HTTP_401_UNAUTHORIZED)


class InsufficientPermissionsError(TenantManagementException):
    """Exception raised when permissions are insufficient."""
    
    def __init__(self, required_permission=None):
        if required_permission:
            detail = f"Insufficient permissions: {required_permission} required"
        else:
            detail = "Insufficient permissions"
        super().__init__(detail, 'insufficient_permissions', status.HTTP_403_FORBIDDEN)


class BillingError(TenantManagementException):
    """Exception raised for billing-related errors."""
    
    def __init__(self, message=None):
        detail = message or "Billing error occurred"
        super().__init__(detail, 'billing_error', status.HTTP_400_BAD_REQUEST)


class InvoiceNotFoundError(TenantManagementException):
    """Exception raised when an invoice is not found."""
    
    def __init__(self, invoice_id=None):
        if invoice_id:
            detail = f"Invoice with ID {invoice_id} not found"
        else:
            detail = "Invoice not found"
        super().__init__(detail, 'invoice_not_found', status.HTTP_404_NOT_FOUND)


class InvoiceAlreadyPaidError(TenantManagementException):
    """Exception raised when an invoice is already paid."""
    
    def __init__(self, invoice_id=None):
        if invoice_id:
            detail = f"Invoice {invoice_id} is already paid"
        else:
            detail = "Invoice is already paid"
        super().__init__(detail, 'invoice_already_paid', status.HTTP_400_BAD_REQUEST)


class PaymentProcessingError(TenantManagementException):
    """Exception raised when payment processing fails."""
    
    def __init__(self, message=None):
        detail = message or "Payment processing failed"
        super().__init__(detail, 'payment_processing_error', status.HTTP_400_BAD_REQUEST)


class ValidationError(TenantManagementException):
    """Exception raised for validation errors."""
    
    def __init__(self, field=None, message=None):
        if field and message:
            detail = f"Validation error for {field}: {message}"
        elif message:
            detail = f"Validation error: {message}"
        else:
            detail = "Validation error"
        super().__init__(detail, 'validation_error', status.HTTP_400_BAD_REQUEST)


class BusinessLogicError(TenantManagementException):
    """Exception raised for business logic violations."""
    
    def __init__(self, message=None):
        detail = message or "Business logic error"
        super().__init__(detail, 'business_logic_error', status.HTTP_422_UNPROCESSABLE_ENTITY)


class ResellerNotFoundError(TenantManagementException):
    """Exception raised when a reseller is not found."""
    
    def __init__(self, reseller_id=None):
        if reseller_id:
            detail = f"Reseller with ID {reseller_id} not found"
        else:
            detail = "Reseller not found"
        super().__init__(detail, 'reseller_not_found', status.HTTP_404_NOT_FOUND)


class ResellerLimitExceededError(TenantManagementException):
    """Exception raised when reseller limits are exceeded."""
    
    def __init__(self, current=None, limit=None):
        if current is not None and limit is not None:
            detail = f"Reseller limit exceeded: {current}/{limit}"
        else:
            detail = "Reseller limit exceeded"
        super().__init__(detail, 'reseller_limit_exceeded', status.HTTP_400_BAD_REQUEST)


class FeatureFlagNotFoundError(TenantManagementException):
    """Exception raised when a feature flag is not found."""
    
    def __init__(self, flag_key=None):
        if flag_key:
            detail = f"Feature flag '{flag_key}' not found"
        else:
            detail = "Feature flag not found"
        super().__init__(detail, 'feature_flag_not_found', status.HTTP_404_NOT_FOUND)


class MetricNotFoundError(TenantManagementException):
    """Exception raised when a metric is not found."""
    
    def __init__(self, metric_id=None):
        if metric_id:
            detail = f"Metric with ID {metric_id} not found"
        else:
            detail = "Metric not found"
        super().__init__(detail, 'metric_not_found', status.HTTP_404_NOT_FOUND)


class HealthScoreNotFoundError(TenantManagementException):
    """Exception raised when a health score is not found."""
    
    def __init__(self, score_id=None):
        if score_id:
            detail = f"Health score with ID {score_id} not found"
        else:
            detail = "Health score not found"
        super().__init__(detail, 'health_score_not_found', status.HTTP_404_NOT_FOUND)


class NotificationNotFoundError(TenantManagementException):
    """Exception raised when a notification is not found."""
    
    def __init__(self, notification_id=None):
        if notification_id:
            detail = f"Notification with ID {notification_id} not found"
        else:
            detail = "Notification not found"
        super().__init__(detail, 'notification_not_found', status.HTTP_404_NOT_FOUND)


class OnboardingNotFoundError(TenantManagementException):
    """Exception raised when onboarding data is not found."""
    
    def __init__(self, onboarding_id=None):
        if onboarding_id:
            detail = f"Onboarding with ID {onboarding_id} not found"
        else:
            detail = "Onboarding not found"
        super().__init__(detail, 'onboarding_not_found', status.HTTP_404_NOT_FOUND)


class TrialExpiredError(TenantManagementException):
    """Exception raised when trial period has expired."""
    
    def __init__(self, tenant_name=None):
        if tenant_name:
            detail = f"Trial period for {tenant_name} has expired"
        else:
            detail = "Trial period has expired"
        super().__init__(detail, 'trial_expired', status.HTTP_403_FORBIDDEN)


class TrialNotActiveError(TenantManagementException):
    """Exception raised when trial is not active."""
    
    def __init__(self):
        detail = "Trial is not active"
        super().__init__(detail, 'trial_not_active', status.HTTP_400_BAD_REQUEST)


class WebhookNotFoundError(TenantManagementException):
    """Exception raised when a webhook is not found."""
    
    def __init__(self, webhook_id=None):
        if webhook_id:
            detail = f"Webhook with ID {webhook_id} not found"
        else:
            detail = "Webhook not found"
        super().__init__(detail, 'webhook_not_found', status.HTTP_404_NOT_FOUND)


class WebhookDeliveryError(TenantManagementException):
    """Exception raised when webhook delivery fails."""
    
    def __init__(self, webhook_url=None, error_message=None):
        if webhook_url and error_message:
            detail = f"Webhook delivery failed to {webhook_url}: {error_message}"
        elif error_message:
            detail = f"Webhook delivery failed: {error_message}"
        else:
            detail = "Webhook delivery failed"
        super().__init__(detail, 'webhook_delivery_error', status.HTTP_400_BAD_REQUEST)


class IPWhitelistNotFoundError(TenantManagementException):
    """Exception raised when IP whitelist entry is not found."""
    
    def __init__(self, ip_id=None):
        if ip_id:
            detail = f"IP whitelist entry with ID {ip_id} not found"
        else:
            detail = "IP whitelist entry not found"
        super().__init__(detail, 'ip_whitelist_not_found', status.HTTP_404_NOT_FOUND)


class IPNotAllowedError(TenantManagementException):
    """Exception raised when IP is not whitelisted."""
    
    def __init__(self, ip_address=None):
        if ip_address:
            detail = f"IP address {ip_address} is not whitelisted"
        else:
            detail = "IP address is not whitelisted"
        super().__init__(detail, 'ip_not_allowed', status.HTTP_403_FORBIDDEN)


class AuditLogNotFoundError(TenantManagementException):
    """Exception raised when audit log is not found."""
    
    def __init__(self, log_id=None):
        if log_id:
            detail = f"Audit log with ID {log_id} not found"
        else:
            detail = "Audit log not found"
        super().__init__(detail, 'audit_log_not_found', status.HTTP_404_NOT_FOUND)


class ConfigurationError(TenantManagementException):
    """Exception raised for configuration errors."""
    
    def __init__(self, setting=None, message=None):
        if setting and message:
            detail = f"Configuration error for {setting}: {message}"
        elif message:
            detail = f"Configuration error: {message}"
        else:
            detail = "Configuration error"
        super().__init__(detail, 'configuration_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceUnavailableError(TenantManagementException):
    """Exception raised when a service is unavailable."""
    
    def __init__(self, service_name=None):
        if service_name:
            detail = f"Service {service_name} is currently unavailable"
        else:
            detail = "Service is currently unavailable"
        super().__init__(detail, 'service_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)


class RateLimitExceededError(TenantManagementException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, limit=None, reset_time=None):
        if limit and reset_time:
            detail = f"Rate limit exceeded: {limit} requests per hour. Resets at {reset_time}"
        elif limit:
            detail = f"Rate limit exceeded: {limit} requests per hour"
        else:
            detail = "Rate limit exceeded"
        super().__init__(detail, 'rate_limit_exceeded', status.HTTP_429_TOO_MANY_REQUESTS)


class DataIntegrityError(TenantManagementException):
    """Exception raised for data integrity issues."""
    
    def __init__(self, message=None):
        detail = message or "Data integrity error"
        super().__init__(detail, 'data_integrity_error', status.HTTP_422_UNPROCESSABLE_ENTITY)


class ExternalServiceError(TenantManagementException):
    """Exception raised for external service errors."""
    
    def __init__(self, service_name=None, error_message=None):
        if service_name and error_message:
            detail = f"External service {service_name} error: {error_message}"
        elif error_message:
            detail = f"External service error: {error_message}"
        else:
            detail = "External service error"
        super().__init__(detail, 'external_service_error', status.HTTP_502_BAD_GATEWAY)


# Custom exception handler for DRF
def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    
    Returns standardized error responses for all exceptions.
    """
    from rest_framework.views import exception_handler
    from rest_framework.response import Response
    from rest_framework import status
    
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        return response
    
    # Handle custom exceptions
    if isinstance(exc, TenantManagementException):
        return Response({
            'success': False,
            'error': exc.detail,
            'code': exc.code,
            'status_code': exc.status_code
        }, status=exc.status_code)
    
    # Handle other exceptions
    return Response({
        'success': False,
        'error': str(exc),
        'code': 'internal_server_error',
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

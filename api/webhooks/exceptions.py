"""
Webhooks Exceptions Module

This module contains custom exceptions for the webhooks system,
provides specific error handling for webhook operations.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class WebhookError(Exception):
    """Base exception for webhook system."""
    pass


class WebhookConfigurationError(WebhookError):
    """Exception raised when webhook configuration is invalid."""
    
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Configuration Error: {self.message}"


class WebhookDispatchError(WebhookError):
    """Exception raised when webhook dispatch fails."""
    
    def __init__(self, message, endpoint_url=None, status_code=None):
        self.message = message
        self.endpoint_url = endpoint_url
        self.status_code = status_code
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Dispatch Error: {self.message}"


class WebhookFilterError(WebhookError):
    """Exception raised when webhook filter evaluation fails."""
    
    def __init__(self, message, filter_rule=None):
        self.message = message
        self.filter_rule = filter_rule
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Filter Error: {self.message}"


class WebhookBatchError(WebhookError):
    """Exception raised when webhook batch processing fails."""
    
    def __init__(self, message, batch_id=None):
        self.message = message
        self.batch_id = batch_id
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Batch Error: {self.message}"


class WebhookReplayError(WebhookError):
    """Exception raised when webhook replay fails."""
    
    def __init__(self, message, replay_id=None):
        self.message = message
        self.replay_id = replay_id
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Replay Error: {self.message}"


class WebhookTemplateError(WebhookError):
    """Exception raised when webhook template processing fails."""
    
    def __init__(self, message, template_name=None):
        self.message = message
        self.template_name = template_name
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Template Error: {self.message}"


class WebhookRateLimitError(WebhookError):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message, endpoint_url=None, retry_after=None):
        self.message = message
        self.endpoint_url = endpoint_url
        self.retry_after = retry_after
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Rate Limit Error: {self.message}"


class WebhookSecurityError(WebhookError):
    """Exception raised when webhook security validation fails."""
    
    def __init__(self, message, security_issue=None):
        self.message = message
        self.security_issue = security_issue
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Security Error: {self.message}"


class WebhookSignatureError(WebhookError):
    """Exception raised when webhook signature verification fails."""
    
    def __init__(self, message, signature_data=None):
        self.message = message
        self.signature_data = signature_data
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Signature Error: {self.message}"


class WebhookHealthCheckError(WebhookError):
    """Exception raised when webhook health check fails."""
    
    def __init__(self, message, endpoint_url=None, response_time=None):
        self.message = message
        self.endpoint_url = endpoint_url
        self.response_time = response_time
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Health Check Error: {self.message}"


class WebhookTimeoutError(WebhookError):
    """Exception raised when webhook operation times out."""
    
    def __init__(self, message, timeout_seconds=None):
        self.message = message
        self.timeout_seconds = timeout_seconds
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Timeout Error: {self.message}"


class WebhookValidationError(ValidationError):
    """Custom validation error for webhook models."""
    
    def __init__(self, message, field=None, code=None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)
    
    def __str__(self):
        return f"Webhook Validation Error: {self.message}"

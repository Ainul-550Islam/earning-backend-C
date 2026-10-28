"""
Webhooks Choices Module

This module contains all choice definitions for the webhooks system,
including model field choices, status options, and configuration enums.
"""

from django.utils.translation import gettext_lazy as _


class WebhookStatus:
    """Webhook endpoint status choices."""
    ACTIVE = 'active'
    PAUSED = 'paused'
    DISABLED = 'disabled'
    SUSPENDED = 'suspended'
    
    CHOICES = [
        (ACTIVE, _('Active')),
        (PAUSED, _('Paused')),
        (DISABLED, _('Disabled')),
        (SUSPENDED, _('Suspended')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class HttpMethod:
    """HTTP method choices for webhook endpoints."""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'
    
    CHOICES = [
        (GET, _('GET')),
        (POST, _('POST')),
        (PUT, _('PUT')),
        (PATCH, _('PATCH')),
        (DELETE, _('DELETE')),
    ]


class DeliveryStatus:
    """Webhook delivery status choices.

    CONSOLIDATED (this audit): previously three independent definitions of
    this same concept existed here, in webhooks/constants.py, and in
    webhooks/models/constants.py (manually kept value-for-value
    consistent). This is now the single owner; the other two re-export
    from here so every existing import path keeps working unchanged.
    """
    PENDING    = 'pending'
    DISPATCHED = 'dispatched'  # BUG FIX: was missing here; present in constants.py's version
    SUCCESS    = 'success'
    FAILED     = 'failed'
    RETRYING   = 'retrying'
    EXPIRED    = 'expired'
    EXHAUSTED = 'exhausted'   # BUG FIX: was missing; used by models/core.py and DispatchService
    CANCELLED = 'cancelled'   # BUG FIX: was missing; used by tasks.py

    CHOICES = [
        (PENDING,    _('Pending')),
        (DISPATCHED, _('Dispatched')),
        (SUCCESS,    _('Success')),
        (FAILED,     _('Failed')),
        (RETRYING,   _('Retrying')),
        (EXPIRED,    _('Expired')),
        (EXHAUSTED, _('Exhausted (Max Retries Reached)')),
        (CANCELLED, _('Cancelled')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class FilterOperator:
    """Filter operator choices for webhook filters.

    CONSOLIDATION (this audit): this used to diverge from
    models/constants.py's FilterOperator in a way that was a live bug, not
    just duplication - GREATER_THAN/LESS_THAN here were 'gt'/'lt' while the
    real WebhookFilter.operator field (models/advanced.py, backed by
    migration 0007) stores 'greater_than'/'less_than'. Since
    services/filtering/FilterService.py compared against this class's
    values, gt/lt filter evaluation was silently always False. Fixed to
    match the real stored values, and added the operators
    models/advanced.py's _LIST_OPERATORS/_VALUELESS_OPERATORS need
    (IN/NOT_IN/EXISTS/NOT_EXISTS/GTE/LTE) that were missing here entirely.
    This is now the single owner; models/constants.py re-exports from here.
    """
    EQUALS = 'equals'
    CONTAINS = 'contains'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    NOT_EQUALS = 'not_equals'
    NOT_CONTAINS = 'not_contains'
    GREATER_THAN_OR_EQUAL = 'gte'
    LESS_THAN_OR_EQUAL = 'lte'
    IN = 'in'
    NOT_IN = 'not_in'
    EXISTS = 'exists'
    NOT_EXISTS = 'not_exists'
    
    CHOICES = [
        (EQUALS, _('Equals')),
        (CONTAINS, _('Contains')),
        (GREATER_THAN, _('Greater Than')),
        (LESS_THAN, _('Less Than')),
        (NOT_EQUALS, _('Not Equals')),
        (NOT_CONTAINS, _('Not Contains')),
        (GREATER_THAN_OR_EQUAL, _('Greater Than or Equal')),
        (LESS_THAN_OR_EQUAL, _('Less Than or Equal')),
        (IN, _('In')),
        (NOT_IN, _('Not In')),
        (EXISTS, _('Exists')),
        (NOT_EXISTS, _('Not Exists')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class BatchStatus:
    """Webhook batch processing status choices."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (PROCESSING, _('Processing')),
        (COMPLETED, _('Completed')),
        (CANCELLED, _('Cancelled')),
        (FAILED, _('Failed')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class ReplayStatus:
    """Webhook replay status choices.

    CONSOLIDATION (this audit): CANCELLED was missing here even though
    WebhookReplayViewSet's cancel action (imports from the top-level
    constants.py, which re-exported this class) sets
    status=ReplayStatus.CANCELLED - confirmed this raised AttributeError on
    every real call. models/constants.py's version already had it. Added.
    """
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (PROCESSING, _('Processing')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
        (CANCELLED, _('Cancelled')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class InboundSource:
    """Inbound webhook source choices."""
    BKASH = 'bkash'
    NAGAD = 'nagad'
    STRIPE = 'stripe'
    PAYPAL = 'paypal'
    ROCKET = 'rocket'
    
    CHOICES = [
        (BKASH, _('bKash')),
        (NAGAD, _('Nagad')),
        (STRIPE, _('Stripe')),
        (PAYPAL, _('PayPal')),
        (ROCKET, _('Rocket')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class ErrorType:
    """Webhook error type choices.

    CONSOLIDATION (this audit): models/constants.py had a separate,
    narrower 'inbound-only' ErrorType (SIGNATURE_ERROR/SYSTEM_ERROR instead
    of AUTHENTICATION_ERROR/AUTHORIZATION_ERROR/RATE_LIMIT_ERROR/
    SERVER_ERROR) that actually governs InboundWebhookError.error_type's
    real field choices. Merged to the union so values written via either
    import path (e.g. InboundWebhookService's ErrorType.AUTHENTICATION_ERROR)
    are valid choices on that field.
    """
    VALIDATION_ERROR = 'validation_error'
    NETWORK_ERROR = 'network_error'
    TIMEOUT_ERROR = 'timeout_error'
    AUTHENTICATION_ERROR = 'authentication_error'
    AUTHORIZATION_ERROR = 'authorization_error'
    RATE_LIMIT_ERROR = 'rate_limit_error'
    SERVER_ERROR = 'server_error'
    UNKNOWN_ERROR = 'unknown_error'
    SIGNATURE_ERROR = 'signature_error'
    SYSTEM_ERROR = 'system_error'
    
    CHOICES = [
        (VALIDATION_ERROR, _('Validation Error')),
        (NETWORK_ERROR, _('Network Error')),
        (TIMEOUT_ERROR, _('Timeout Error')),
        (AUTHENTICATION_ERROR, _('Authentication Error')),
        (AUTHORIZATION_ERROR, _('Authorization Error')),
        (RATE_LIMIT_ERROR, _('Rate Limit Error')),
        (SERVER_ERROR, _('Server Error')),
        (UNKNOWN_ERROR, _('Unknown Error')),
        (SIGNATURE_ERROR, _('Signature Error')),
        (SYSTEM_ERROR, _('System Error')),
    ]
    choices = CHOICES  # lowercase alias for code expecting Django TextChoices-style access


class RetryPolicy:
    """Webhook retry policy choices."""
    EXPONENTIAL_BACKOFF = 'exponential_backoff'
    LINEAR_BACKOFF = 'linear_backoff'
    FIXED_INTERVAL = 'fixed_interval'
    
    CHOICES = [
        (EXPONENTIAL_BACKOFF, _('Exponential Backoff')),
        (LINEAR_BACKOFF, _('Linear Backoff')),
        (FIXED_INTERVAL, _('Fixed Interval')),
    ]


class RateLimitPolicy:
    """Rate limiting policy choices."""
    PER_ENDPOINT = 'per_endpoint'
    PER_USER = 'per_user'
    PER_IP = 'per_ip'
    GLOBAL = 'global'
    
    CHOICES = [
        (PER_ENDPOINT, _('Per Endpoint')),
        (PER_USER, _('Per User')),
        (PER_IP, _('Per IP Address')),
        (GLOBAL, _('Global')),
    ]


class SecurityLevel:
    """Webhook security level choices."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, _('Low')),
        (MEDIUM, _('Medium')),
        (HIGH, _('High')),
        (CRITICAL, _('Critical')),
    ]


class LogLevel:
    """Webhook log level choices."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    
    CHOICES = [
        (DEBUG, _('Debug')),
        (INFO, _('Info')),
        (WARNING, _('Warning')),
        (ERROR, _('Error')),
        (CRITICAL, _('Critical')),
    ]

# All choice classes available for model field choices
__all__ = [
    'RetryPolicy',
    'RateLimitPolicy',
    'SecurityLevel',
]

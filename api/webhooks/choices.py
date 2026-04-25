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
    """Webhook delivery status choices."""
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'
    RETRYING = 'retrying'
    EXPIRED = 'expired'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (SUCCESS, _('Success')),
        (FAILED, _('Failed')),
        (RETRYING, _('Retrying')),
        (EXPIRED, _('Expired')),
    ]


class FilterOperator:
    """Filter operator choices for webhook filters."""
    EQUALS = 'equals'
    CONTAINS = 'contains'
    GREATER_THAN = 'gt'
    LESS_THAN = 'lt'
    NOT_EQUALS = 'not_equals'
    NOT_CONTAINS = 'not_contains'
    
    CHOICES = [
        (EQUALS, _('Equals')),
        (CONTAINS, _('Contains')),
        (GREATER_THAN, _('Greater Than')),
        (LESS_THAN, _('Less Than')),
        (NOT_EQUALS, _('Not Equals')),
        (NOT_CONTAINS, _('Not Contains')),
    ]


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


class ReplayStatus:
    """Webhook replay status choices."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (PROCESSING, _('Processing')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
    ]


class InboundSource:
    """Inbound webhook source choices."""
    BKASH = 'bkash'
    NAGAD = 'nagad'
    STRIPE = 'stripe'
    PAYPAL = 'paypal'
    
    CHOICES = [
        (BKASH, _('bKash')),
        (NAGAD, _('Nagad')),
        (STRIPE, _('Stripe')),
        (PAYPAL, _('PayPal')),
    ]


class ErrorType:
    """Webhook error type choices."""
    VALIDATION_ERROR = 'validation_error'
    NETWORK_ERROR = 'network_error'
    TIMEOUT_ERROR = 'timeout_error'
    AUTHENTICATION_ERROR = 'authentication_error'
    AUTHORIZATION_ERROR = 'authorization_error'
    RATE_LIMIT_ERROR = 'rate_limit_error'
    SERVER_ERROR = 'server_error'
    UNKNOWN_ERROR = 'unknown_error'
    
    CHOICES = [
        (VALIDATION_ERROR, _('Validation Error')),
        (NETWORK_ERROR, _('Network Error')),
        (TIMEOUT_ERROR, _('Timeout Error')),
        (AUTHENTICATION_ERROR, _('Authentication Error')),
        (AUTHORIZATION_ERROR, _('Authorization Error')),
        (RATE_LIMIT_ERROR, _('Rate Limit Error')),
        (SERVER_ERROR, _('Server Error')),
        (UNKNOWN_ERROR, _('Unknown Error')),
    ]


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

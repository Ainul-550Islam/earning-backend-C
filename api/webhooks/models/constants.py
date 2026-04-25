"""Webhook Model Constants

This module contains constants and choices used by webhook models.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class WebhookStatus(models.TextChoices):
    """Webhook endpoint status choices."""
    ACTIVE = 'active', _('Active')
    PAUSED = 'paused', _('Paused')
    INACTIVE = 'inactive', _('Inactive')
    SUSPENDED = 'suspended', _('Suspended')


class DeliveryStatus(models.TextChoices):
    """Webhook delivery status choices."""
    PENDING = 'pending', _('Pending')
    SUCCESS = 'success', _('Success')
    FAILED = 'failed', _('Failed')
    RETRYING = 'retrying', _('Retrying')
    EXHAUSTED = 'exhausted', _('Exhausted')


class BatchStatus(models.TextChoices):
    """Webhook batch status choices."""
    PENDING = 'pending', _('Pending')
    PROCESSING = 'processing', _('Processing')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
    CANCELLED = 'cancelled', _('Cancelled')


class FilterOperator(models.TextChoices):
    """Webhook filter operator choices."""
    EQUALS = 'equals', _('Equals')
    NOT_EQUALS = 'not_equals', _('Not Equals')
    CONTAINS = 'contains', _('Contains')
    NOT_CONTAINS = 'not_contains', _('Not Contains')
    GREATER_THAN = 'greater_than', _('Greater Than')
    LESS_THAN = 'less_than', _('Less Than')
    GREATER_THAN_OR_EQUAL = 'gte', _('Greater Than or Equal')
    LESS_THAN_OR_EQUAL = 'lte', _('Less Than or Equal')
    IN = 'in', _('In')
    NOT_IN = 'not_in', _('Not In')
    EXISTS = 'exists', _('Exists')
    NOT_EXISTS = 'not_exists', _('Not Exists')


class InboundSource(models.TextChoices):
    """Inbound webhook source choices."""
    BKASH = 'bkash', _('bKash')
    NAGAD = 'nagad', _('Nagad')
    STRIPE = 'stripe', _('Stripe')
    PAYPAL = 'paypal', _('PayPal')
    CUSTOM = 'custom', _('Custom')


class ReplayStatus(models.TextChoices):
    """Webhook replay status choices."""
    PENDING = 'pending', _('Pending')
    PROCESSING = 'processing', _('Processing')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
    CANCELLED = 'cancelled', _('Cancelled')


class ErrorType(models.TextChoices):
    """Inbound webhook error type choices."""
    VALIDATION_ERROR = 'validation_error', _('Validation Error')
    SIGNATURE_ERROR = 'signature_error', _('Signature Error')
    TIMEOUT_ERROR = 'timeout_error', _('Timeout Error')
    NETWORK_ERROR = 'network_error', _('Network Error')
    SYSTEM_ERROR = 'system_error', _('System Error')
    UNKNOWN_ERROR = 'unknown_error', _('Unknown Error')


# HTTP Method Choices
HTTP_METHOD_CHOICES = [
    ('POST', 'POST'),
    ('PUT', 'PUT'),
    ('PATCH', 'PATCH'),
]

# Default values
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_PER_MIN = 60
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_BATCH_SIZE = 1000

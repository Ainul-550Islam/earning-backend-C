"""Core Webhook Models

This module contains the core webhook models including WebhookEndpoint,
WebhookSubscription, and WebhookDeliveryLog with enhanced features.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..choices import WebhookStatus, DeliveryStatus

User = get_user_model()


class WebhookEndpoint(models.Model):
    """Webhook endpoint model for managing webhook destinations."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=255, help_text="Human-readable label for the endpoint")
    url = models.URLField(max_length=2048, help_text="Webhook URL to send events to", blank=True, default='')
    description = models.TextField(blank=True, help_text="Description of the endpoint's purpose")
    
    # Owner and status
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='webhook_endpoints',
        help_text="User who owns this webhook endpoint"
    )
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.CHOICES,
        default=WebhookStatus.ACTIVE,
        help_text="Current status of the webhook endpoint"
    )
    
    # HTTP configuration
    http_method = models.CharField(
        max_length=10,
        default='POST',
        choices=[
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
        ],
        help_text="HTTP method to use for webhook requests"
    )
    timeout_seconds = models.IntegerField(
        default=30,
        help_text="Timeout in seconds for webhook requests"
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum number of retry attempts"
    )
    verify_ssl = models.BooleanField(
        default=True,
        help_text="Whether to verify SSL certificates"
    )
    
    # Enhanced features
    ip_whitelist = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses for webhook requests"
    )
    rate_limit_per_min = models.IntegerField(
        default=60,
        help_text="Rate limit per minute for this endpoint"
    )
    payload_template = models.ForeignKey(
        'WebhookTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='endpoints',
        help_text="Template to use for payload transformation"
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom headers to include in webhook requests"
    )
    
    # Security
    secret_key = models.CharField(
        max_length=255,
        help_text="Secret key for signing webhook payloads"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    
    # Suspension tracking
    suspension_reason = models.TextField(blank=True, help_text="Reason for suspension")
    
    class Meta:
        db_table = 'webhook_endpoints'
        verbose_name = 'Webhook Endpoint'
        verbose_name_plural = 'Webhook Endpoints'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status'], name='idx_owner_status_1905'),
            models.Index(fields=['status'], name='idx_status_1906'),
            models.Index(fields=['created_at'], name='idx_created_at_1907'),
        ]
    
    def __str__(self):
        return f"{self.label or self.url} ({self.get_status_display()})"
    
    def clean(self):
        """Validate the webhook endpoint."""
        super().clean()
        
        # Validate URL
        if self.url and not self.url.startswith(('http://', 'https://')):
            raise ValidationError("URL must start with http:// or https://")
        
        # Validate timeout
        if self.timeout_seconds <= 0:
            raise ValidationError("Timeout must be greater than 0")
        
        # Validate max retries
        if self.max_retries < 0:
            raise ValidationError("Max retries must be non-negative")
        
        # Validate rate limit
        if self.rate_limit_per_min <= 0:
            raise ValidationError("Rate limit must be greater than 0")
    
    def is_active(self):
        """Check if endpoint is active."""
        return self.status == WebhookStatus.ACTIVE
    
    def is_suspended(self):
        """Check if endpoint is suspended."""
        return self.status == WebhookStatus.SUSPENDED
    
    def get_subscription_count(self):
        """Get the number of active subscriptions."""
        return self.subscriptions.filter(is_active=True).count()
    
    def get_recent_deliveries(self, days=7):
        """Get recent delivery logs."""
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return self.delivery_logs.filter(created_at__gte=since)


class WebhookSubscription(models.Model):
    """Webhook subscription model for managing event subscriptions."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        help_text="Webhook endpoint to send events to"
    )
    event_type = models.CharField(
        max_length=255,
        help_text="Event type to subscribe to"
    )
    filter_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter configuration for conditional event delivery"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this subscription is active"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_subscriptions'
        verbose_name = 'Webhook Subscription'
        verbose_name_plural = 'Webhook Subscriptions'
        ordering = ['-created_at']
        unique_together = [['endpoint', 'event_type']]
        indexes = [
            models.Index(fields=['endpoint', 'is_active'], name='idx_endpoint_is_active_1908'),
            models.Index(fields=['event_type'], name='idx_event_type_1909'),
            models.Index(fields=['is_active'], name='idx_is_active_1910'),
        ]
    
    def __str__(self):
        return f"{self.endpoint.label} - {self.event_type}"
    
    def clean(self):
        """Validate the webhook subscription."""
        super().clean()
        
        # Validate event type
        if not self.event_type:
            raise ValidationError("Event type is required")
        
        # Validate filter config
        if self.filter_config and not isinstance(self.filter_config, dict):
            raise ValidationError("Filter configuration must be a dictionary")
    
    def matches_event(self, event_data):
        """Check if this subscription matches the event data."""
        if not self.is_active:
            return False
        
        if self.event_type != event_data.get('event_type'):
            return False
        
        # Apply filter if configured
        if self.filter_config:
            from ..services.filtering import FilterService
            filter_service = FilterService()
            return filter_service.evaluate_filter_config(self.filter_config, event_data)
        
        return True


class WebhookDeliveryLog(models.Model):
    """Webhook delivery log model for tracking webhook delivery attempts."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name='delivery_logs',
        help_text="Webhook endpoint that received the delivery"
    )
    event_type = models.CharField(
        max_length=255,
        help_text="Type of event that was delivered"
    )
    payload = models.JSONField(
        help_text="Payload that was sent in the webhook request"
    )
    
    # Request details
    request_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Headers sent with the webhook request"
    )
    signature = models.CharField(
        max_length=255,
        blank=True,
        help_text="Signature used for webhook request"
    )
    
    # Response details
    http_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code returned by the endpoint"
    )
    response_body = models.TextField(
        blank=True,
        help_text="Response body returned by the endpoint"
    )
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the webhook request in milliseconds"
    )
    
    # Status and retry information
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.CHOICES,
        default=DeliveryStatus.PENDING,
        help_text="Current status of the delivery"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed"
    )
    attempt_number = models.IntegerField(
        default=1,
        help_text="Current attempt number"
    )
    max_attempts = models.IntegerField(
        default=3,
        help_text="Maximum number of attempts allowed"
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp for next retry attempt"
    )
    
    # Timestamps
    dispatched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the webhook was dispatched"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the delivery was completed"
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_delivery_logs'
        verbose_name = 'Webhook Delivery Log'
        verbose_name_plural = 'Webhook Delivery Logs'
        ordering = ['-dispatched_at']
        indexes = [
            models.Index(fields=['endpoint', 'status'], name='idx_endpoint_status_1911'),
            models.Index(fields=['event_type'], name='idx_event_type_1912'),
            models.Index(fields=['status'], name='idx_status_1913'),
            models.Index(fields=['dispatched_at'], name='idx_dispatched_at_1914'),
            models.Index(fields=['next_retry_at'], name='idx_next_retry_at_1915'),
        ]
    
    def __str__(self):
        return f"{self.endpoint.label} - {self.event_type} ({self.get_status_display()})"
    
    def is_successful(self):
        """Check if delivery was successful."""
        return self.status == DeliveryStatus.SUCCESS
    
    def is_failed(self):
        """Check if delivery failed."""
        return self.status == DeliveryStatus.FAILED
    
    def is_exhausted(self):
        """Check if retry attempts are exhausted."""
        return self.status == DeliveryStatus.EXHAUSTED
    
    def can_retry(self):
        """Check if delivery can be retried."""
        return (
            self.is_failed() and 
            self.attempt_number < self.max_attempts and
            (self.next_retry_at is None or self.next_retry_at <= timezone.now())
        )
    
    def get_retry_delay(self):
        """Calculate retry delay using exponential backoff."""
        if self.attempt_number <= 1:
            return 60  # 1 minute
        elif self.attempt_number <= 2:
            return 300  # 5 minutes
        else:
            return 900  # 15 minutes
    
    def schedule_retry(self):
        """Schedule next retry attempt."""
        if self.can_retry():
            from datetime import timedelta
            delay = self.get_retry_delay()
            self.next_retry_at = timezone.now() + timedelta(seconds=delay)
            self.status = DeliveryStatus.RETRYING
            self.save()
            return True
        return False
    
    def mark_as_successful(self, status_code=None, response_body=None, duration_ms=None):
        """Mark delivery as successful."""
        self.status = DeliveryStatus.SUCCESS
        self.http_status_code = status_code
        self.response_body = response_body or ''
        self.duration_ms = duration_ms
        self.completed_at = timezone.now()
        self.save()
    
    def mark_as_failed(self, error_message, status_code=None, response_body=None, duration_ms=None):
        """Mark delivery as failed."""
        self.status = DeliveryStatus.FAILED
        self.error_message = error_message
        self.http_status_code = status_code
        self.response_body = response_body or ''
        self.duration_ms = duration_ms
        self.completed_at = timezone.now()
        
        # Check if retries are exhausted
        if self.attempt_number >= self.max_attempts:
            self.status = DeliveryStatus.EXHAUSTED
        
        self.save()
    
    def mark_as_exhausted(self, error_message):
        """Mark delivery as exhausted (no more retries)."""
        self.status = DeliveryStatus.EXHAUSTED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()

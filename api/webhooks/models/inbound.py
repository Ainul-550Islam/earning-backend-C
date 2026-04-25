"""
Inbound Webhook Models

This module contains models for receiving external webhooks
from payment gateways and other external systems.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .constants import (
    InboundSource, ErrorType
)

User = get_user_model()


class InboundWebhook(models.Model):
    """
    Configuration for inbound webhook receivers.
    Handles webhooks from external payment gateways and systems.
    """
    
    source = models.CharField(
        max_length=50,
        choices=InboundSource.choices,
        verbose_name=_('Source'),
        help_text=_('Payment gateway or external system')
    )
    url_token = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('URL Token'),
        help_text=_('Unique token for webhook URL')
    )
    secret = models.CharField(
        max_length=255,
        verbose_name=_('Secret'),
        help_text=_('Secret key for signature verification')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_inbound_webhooks',
        verbose_name=_('Created By'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Inbound Webhook')
        verbose_name_plural = _('Inbound Webhooks')
        indexes = [
            models.Index(fields=['source', 'is_active'], name='iw_source_active_idx'),
            models.Index(fields=['url_token'], name='iw_url_token_idx'),
            models.Index(fields=['created_at'], name='iw_created_at_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Inbound webhook from {self.get_source_display()} ({self.url_token})"
    
    def get_webhook_url(self) -> str:
        """Generate the full webhook URL."""
        return f"/api/v1/webhooks/inbound/{self.url_token}/"


class InboundWebhookLog(models.Model):
    """
    Log of inbound webhook requests.
    Tracks all incoming webhook requests for audit and debugging.
    """
    
    inbound = models.ForeignKey(
        InboundWebhook,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name=_('Inbound Webhook'),
    )
    raw_payload = models.JSONField(
        verbose_name=_('Raw Payload'),
        help_text=_('Original webhook payload as received')
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Headers'),
        help_text=_('HTTP headers from webhook request')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address'),
        help_text=_('IP address of webhook sender')
    )
    signature_valid = models.BooleanField(
        default=False,
        verbose_name=_('Signature Valid'),
        help_text=_('Whether webhook signature was valid')
    )
    processed = models.BooleanField(
        default=False,
        verbose_name=_('Processed'),
        help_text=_('Whether webhook has been processed')
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processed At'),
        help_text=_('When webhook was processed')
    )
    error_message = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Error Message'),
        help_text=_('Error message if processing failed')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    
    class Meta:
        verbose_name = _('Inbound Webhook Log')
        verbose_name_plural = _('Inbound Webhook Logs')
        indexes = [
            models.Index(fields=['inbound', 'created_at'], name='iwl_inbound_created_idx'),
            models.Index(fields=['signature_valid'], name='iwl_signature_valid_idx'),
            models.Index(fields=['processed'], name='iwl_processed_idx'),
            models.Index(fields=['ip_address'], name='iwl_ip_address_idx'),
        ]
    
    def __str__(self) -> str:
        status = "Processed" if self.processed else "Pending"
        return f"Log {self.id} ({status})"


class InboundWebhookRoute(models.Model):
    """
    Routing configuration for inbound webhooks.
    Maps incoming webhooks to handler functions.
    """
    
    inbound = models.ForeignKey(
        InboundWebhook,
        on_delete=models.CASCADE,
        related_name='routes',
        verbose_name=_('Inbound Webhook'),
    )
    event_pattern = models.CharField(
        max_length=255,
        verbose_name=_('Event Pattern'),
        help_text=_('Regex or pattern to match events')
    )
    handler_function = models.CharField(
        max_length=255,
        verbose_name=_('Handler Function'),
        help_text=_('Python function to handle matching events')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
    )
    priority = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        verbose_name=_('Priority'),
        help_text=_('Lower numbers have higher priority')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Inbound Webhook Route')
        verbose_name_plural = _('Inbound Webhook Routes')
        indexes = [
            models.Index(fields=['inbound', 'is_active'], name='iwr_inbound_active_idx'),
            models.Index(fields=['priority'], name='iwr_priority_idx'),
            models.Index(fields=['event_pattern'], name='iwr_event_pattern_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Route {self.event_pattern} -> {self.handler_function}"


class InboundWebhookError(models.Model):
    """
    Error tracking for inbound webhook processing.
    Logs errors for debugging and monitoring.
    """
    
    log = models.ForeignKey(
        InboundWebhookLog,
        on_delete=models.CASCADE,
        related_name='errors',
        verbose_name=_('Webhook Log'),
    )
    error_type = models.CharField(
        max_length=50,
        choices=ErrorType.choices,
        verbose_name=_('Error Type'),
    )
    error_message = models.TextField(
        verbose_name=_('Error Message'),
        help_text=_('Detailed error description')
    )
    stack_trace = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Stack Trace'),
        help_text=_('Full stack trace for debugging')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    
    class Meta:
        verbose_name = _('Inbound Webhook Error')
        verbose_name_plural = _('Inbound Webhook Errors')
        indexes = [
            models.Index(fields=['log', 'error_type'], name='iwe_log_error_idx'),
            models.Index(fields=['error_type'], name='iwe_error_type_idx'),
            models.Index(fields=['created_at'], name='iwe_created_at_idx'),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_error_type_display()}: {self.error_message[:50]}"

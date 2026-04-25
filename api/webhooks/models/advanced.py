"""
Advanced Models for Webhooks System

This module contains advanced webhook models including filters, batches,
templates, and secrets management.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .constants import (
    FilterOperator, BatchStatus
)

User = get_user_model()


class WebhookFilter(models.Model):
    """
    Advanced filtering rules for webhook events.
    Controls which events trigger webhook deliveries.
    """
    
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='filters',
        verbose_name=_('Endpoint'),
    )
    field_path = models.CharField(
        max_length=255,
        verbose_name=_('Field Path'),
        help_text=_('JSON field path to filter (e.g., "user.email", "amount")')
    )
    operator = models.CharField(
        max_length=20,
        choices=FilterOperator.choices,
        default=FilterOperator.EQUALS,
        verbose_name=_('Operator'),
    )
    value = models.JSONField(
        verbose_name=_('Value'),
        help_text=_('Filter value (supports strings, numbers, arrays)')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
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
        verbose_name = _('Webhook Filter')
        verbose_name_plural = _('Webhook Filters')
        indexes = [
            models.Index(fields=['endpoint', 'is_active'], name='wf_endpoint_active_idx'),
            models.Index(fields=['field_path'], name='wf_field_path_idx'),
        ]
    
    def __str__(self) -> str:
        return f"{self.field_path} {self.operator} {self.value}"
    
    def clean(self):
        """Validate filter configuration."""
        if not self.field_path:
            raise ValidationError(_('Field path is required'))
        
        if self.operator not in [choice[0] for choice in FilterOperator.choices]:
            raise ValidationError(_('Invalid operator'))


class WebhookBatch(models.Model):
    """
    Batch processing for webhook deliveries.
    Groups multiple webhook events for efficient processing.
    """
    
    batch_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Batch ID'),
    )
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name=_('Endpoint'),
    )
    event_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Event Count'),
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name=_('Status'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Batch')
        verbose_name_plural = _('Webhook Batches')
        indexes = [
            models.Index(fields=['batch_id'], name='wb_batch_id_idx'),
            models.Index(fields=['endpoint', 'status'], name='wb_endpoint_status_idx'),
            models.Index(fields=['created_at'], name='wb_created_at_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Batch {self.batch_id} ({self.event_count} events)"


class WebhookBatchItem(models.Model):
    """
    Individual items within a webhook batch.
    Links batch items to delivery logs.
    """
    
    batch = models.ForeignKey(
        WebhookBatch,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('Batch'),
    )
    delivery_log = models.ForeignKey(
        'WebhookDeliveryLog',
        on_delete=models.CASCADE,
        related_name='batch_items',
        verbose_name=_('Delivery Log'),
    )
    position = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_('Position'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Batch Item')
        verbose_name_plural = _('Webhook Batch Items')
        indexes = [
            models.Index(fields=['batch', 'position'], name='wbi_batch_position_idx'),
            models.Index(fields=['delivery_log'], name='wbi_delivery_log_idx'),
        ]
        unique_together = [
            ['batch', 'delivery_log'],
        ]
    
    def __str__(self) -> str:
        return f"Item {self.position} in batch {self.batch.batch_id}"


class WebhookTemplate(models.Model):
    """
    Template engine for webhook payloads.
    Supports Jinja2 templating and transformation rules.
    """
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Template Name'),
    )
    event_type = models.CharField(
        max_length=100,
        verbose_name=_('Event Type'),
        help_text=_('Event type this template applies to')
    )
    payload_template = models.TextField(
        verbose_name=_('Payload Template'),
        help_text=_('Jinja2 template for payload transformation')
    )
    transform_rules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Transform Rules'),
        help_text=_('JSON transformation rules applied before template')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
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
        verbose_name = _('Webhook Template')
        verbose_name_plural = _('Webhook Templates')
        indexes = [
            models.Index(fields=['event_type', 'is_active'], name='wt_event_active_idx'),
            models.Index(fields=['name'], name='wt_name_idx'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.event_type})"


class WebhookSecret(models.Model):
    """
    Secret management for webhook endpoints.
    Supports secret rotation and grace periods.
    """
    
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='secrets',
        verbose_name=_('Endpoint'),
    )
    secret_hash = models.CharField(
        max_length=255,
        verbose_name=_('Secret Hash'),
        help_text=_('Hashed version of the webhook secret')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Expires At'),
        help_text=_('When this secret expires (for rotation)')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
    )
    
    class Meta:
        verbose_name = _('Webhook Secret')
        verbose_name_plural = _('Webhook Secrets')
        indexes = [
            models.Index(fields=['endpoint', 'is_active'], name='ws_endpoint_active_idx'),
            models.Index(fields=['expires_at'], name='ws_expires_at_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Secret for {self.endpoint.url} (expires: {self.expires_at})"
    
    def is_expired(self) -> bool:
        """Check if secret is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
